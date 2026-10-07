"""구독 해지 테스트: 즉시 해지돼도 이미 결제한 기간이 끝날 때까지 PRO를 유지한다."""
import os

os.environ["SENTRY_DSN"] = ""

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
import webhook
from billing import expire_due_plans, expire_if_due
from models import Base, User, PlanType

SECRET = "test-webhook-secret"


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.fixture()
def setup(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    user = User(google_user_id="g1", email="payer@example.com", plan=PlanType.BASIC)
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", SECRET)
    monkeypatch.delenv("PADDLE_API_KEY", raising=False)
    main.app.dependency_overrides[main.get_db] = override_get_db
    client = TestClient(main.app)

    def send(event_type, data):
        body = json.dumps({"event_type": event_type, "data": data})
        ts = str(int(time.time()))
        h1 = hmac.new(SECRET.encode(), f"{ts}:{body}".encode(), hashlib.sha256).hexdigest()
        res = client.post("/api/webhook/paddle", content=body, headers={"Paddle-Signature": f"ts={ts};h1={h1}", "Content-Type": "application/json"})
        assert res.status_code == 200

    def load():
        session = SessionLocal()
        try:
            return session.query(User).filter(User.id == user_id).first()
        finally:
            session.close()

    yield send, load, user_id, SessionLocal, client
    main.app.dependency_overrides.pop(main.get_db, None)
    engine.dispose()


def _pay(send, user_id, ends_at):
    send("transaction.completed", {
        "custom_data": {"user_id": str(user_id)},
        "customer_id": "ctm_1",
        "subscription_id": "sub_1",
        "billing_period": {"starts_at": _iso(ends_at - timedelta(days=30)), "ends_at": _iso(ends_at)},
    })


def test_immediate_cancel_keeps_pro_until_the_paid_period_ends(setup):
    send, load, user_id, *_ = setup
    ends_at = datetime.now(timezone.utc) + timedelta(days=20)
    _pay(send, user_id, ends_at)
    assert load().plan == PlanType.PRO

    # 즉시 해지: Paddle은 current_billing_period를 null로 보낸다
    send("subscription.canceled", {"id": "sub_1", "status": "canceled", "current_billing_period": None})

    user = load()
    assert user.plan == PlanType.PRO
    assert abs((user.pro_until - ends_at).total_seconds()) < 1


def test_cancel_after_the_paid_period_downgrades_right_away(setup):
    send, load, user_id, *_ = setup
    _pay(send, user_id, datetime.now(timezone.utc) - timedelta(minutes=1))

    # 기간 끝에 맞춰 해지(예약 해지)되는 일반적인 경우 - 남은 기간이 없으니 바로 BASIC
    send("subscription.canceled", {"id": "sub_1", "status": "canceled", "current_billing_period": None})

    user = load()
    assert user.plan == PlanType.BASIC and user.pro_until is None


def test_cancel_without_known_period_downgrades_like_before(setup):
    send, load, user_id, SessionLocal, _ = setup
    session = SessionLocal()
    user = session.query(User).filter(User.id == user_id).first()
    user.plan, user.stripe_subscription_id = PlanType.PRO, "sub_old"
    session.commit()
    session.close()

    # 이 기능 전에 결제했고 Paddle 조회도 안 되면(API 키 없음) 예전처럼 바로 내린다
    send("subscription.canceled", {"id": "sub_old", "status": "canceled"})
    assert load().plan == PlanType.BASIC


def test_cancel_looks_up_the_last_payment_when_period_is_unknown(setup, monkeypatch):
    send, load, user_id, SessionLocal, _ = setup
    session = SessionLocal()
    user = session.query(User).filter(User.id == user_id).first()
    user.plan, user.stripe_subscription_id = PlanType.PRO, "sub_old"
    session.commit()
    session.close()

    ends_at = datetime.now(timezone.utc) + timedelta(days=5)

    async def fake_fetch(subscription_id):
        assert subscription_id == "sub_old"
        return ends_at

    monkeypatch.setattr(webhook, "_fetch_paid_until", fake_fetch)
    send("subscription.canceled", {"id": "sub_old", "status": "canceled"})

    user = load()
    assert user.plan == PlanType.PRO and abs((user.pro_until - ends_at).total_seconds()) < 1


def test_renewal_extends_the_paid_period(setup):
    send, load, user_id, *_ = setup
    first_end = datetime.now(timezone.utc) + timedelta(days=1)
    _pay(send, user_id, first_end)

    next_end = first_end + timedelta(days=30)
    send("subscription.updated", {"id": "sub_1", "status": "active", "current_billing_period": {"ends_at": _iso(next_end)}})
    assert abs((load().paid_until - next_end).total_seconds()) < 1

    # 순서가 뒤바뀌어 옛 결제 알림이 늦게 와도 결제 기간을 앞당기지 않는다
    _pay(send, user_id, first_end)
    assert abs((load().paid_until - next_end).total_seconds()) < 1


def test_paying_again_cancels_the_scheduled_downgrade(setup):
    send, load, user_id, *_ = setup
    _pay(send, user_id, datetime.now(timezone.utc) + timedelta(days=3))
    send("subscription.canceled", {"id": "sub_1", "status": "canceled"})
    assert load().pro_until is not None

    _pay(send, user_id, datetime.now(timezone.utc) + timedelta(days=30))
    user = load()
    assert user.plan == PlanType.PRO and user.pro_until is None


def test_expired_canceled_plans_drop_to_basic(db_session):
    now = datetime.now(timezone.utc)
    expired = User(email="a@example.com", plan=PlanType.PRO, pro_until=now - timedelta(minutes=1))
    still_paid = User(email="b@example.com", plan=PlanType.PRO, pro_until=now + timedelta(days=2))
    active = User(email="c@example.com", plan=PlanType.PRO)
    db_session.add_all([expired, still_paid, active])
    db_session.commit()

    assert expire_due_plans(db_session, now) == 1
    assert expired.plan == PlanType.BASIC and expired.pro_until is None
    assert still_paid.plan == PlanType.PRO
    assert active.plan == PlanType.PRO
    assert expire_if_due(active, now) is False


def test_profile_shows_when_pro_ends_and_downgrades_once_it_passes(setup):
    send, load, user_id, SessionLocal, client = setup
    ends_at = datetime.now(timezone.utc) + timedelta(days=10)
    _pay(send, user_id, ends_at)
    send("subscription.canceled", {"id": "sub_1", "status": "canceled"})

    client.cookies.set("auth_token", main.create_access_token(user_id, None))
    me = client.get("/api/user/me").json()
    assert me["is_pro"] is True and me["pro_until"].startswith(ends_at.date().isoformat())

    session = SessionLocal()
    user = session.query(User).filter(User.id == user_id).first()
    user.pro_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.commit()
    session.close()

    me = client.get("/api/user/me").json()
    assert me["is_pro"] is False and me["pro_until"] is None
    assert load().plan == PlanType.BASIC
