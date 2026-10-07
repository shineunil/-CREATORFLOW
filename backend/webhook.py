from fastapi import APIRouter, Request, HTTPException, Depends
import os, logging, hmac, hashlib, json
from datetime import datetime, timezone
import httpx
from sqlalchemy.orm import Session
from database import get_db
from models import User
from env_utils import is_dev_environment
from billing import end_subscription, period_end_of, record_paid_period, resume_subscription

logger = logging.getLogger(__name__)
router = APIRouter()


def _verify_paddle_signature(body: bytes, header: str, secret: str) -> bool:
    """Paddle v2 웹훅 서명 검증. header 형식: ts=TIMESTAMP;h1=HMAC_SHA256"""
    try:
        parts = dict(p.split("=", 1) for p in header.split(";"))
        ts = parts.get("ts", "")
        h1 = parts.get("h1", "")
        signed = f"{ts}:{body.decode()}"
        expected = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, h1)
    except Exception:
        return False


@router.post("/api/webhook/paddle")
async def paddle_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    sig_header = request.headers.get("Paddle-Signature", "")
    secret = os.getenv("PADDLE_WEBHOOK_SECRET", "")

    if not secret and not is_dev_environment():
        logger.error("[Paddle Webhook] PADDLE_WEBHOOK_SECRET 미설정 - 서명 검증 불가로 요청 거부")
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    if secret:
        if not _verify_paddle_signature(body, sig_header, secret):
            logger.warning("[Paddle Webhook] 🚨 서명 검증 실패 - 위조 요청 차단!")
            raise HTTPException(status_code=400, detail="Invalid Paddle webhook signature")

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = event.get("event_type", "")
    data = event.get("data", {})
    logger.info(f"[Paddle Webhook] 이벤트 수신: {event_type}")

    if event_type == "transaction.completed":
        custom_data = data.get("custom_data") or {}
        user_id = custom_data.get("user_id")
        customer_id = data.get("customer_id")
        subscription_id = data.get("subscription_id")

        user = None
        if user_id:
            try:
                user = db.query(User).filter(User.id == int(user_id)).first()
            except (ValueError, TypeError):
                pass
        if user is None and subscription_id:
            # 갱신 결제에 custom_data가 빠져 와도 구독 ID로 찾는다
            user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first()

        if user:
            resume_subscription(user)
            record_paid_period(user, data)
            if customer_id:
                user.stripe_customer_id = customer_id    # Paddle customer ID 재사용
            if subscription_id:
                user.stripe_subscription_id = subscription_id  # Paddle subscription ID 재사용
            db.commit()
            logger.info(f"[Paddle Webhook] ✅ user_id={user.id} ({user.email}) → PRO (결제 기간 끝: {user.paid_until})")
        else:
            logger.warning(f"[Paddle Webhook] 유저 찾기 실패 (user_id={user_id})")

    elif event_type in ("subscription.canceled", "subscription.paused"):
        subscription_id = data.get("id")
        user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first() if subscription_id else None
        if user:
            if user.paid_until is None:
                # 이 기능 전에 결제한 유저는 결제 기간이 저장돼 있지 않다 - Paddle에서 마지막 결제를 조회
                fetched = await _fetch_paid_until(subscription_id)
                if fetched:
                    user.paid_until = fetched
            keep_until = end_subscription(user, datetime.now(timezone.utc))
            db.commit()
            if keep_until:
                logger.info(f"[Paddle Webhook] ⏳ user_id={user.id} 구독 종료 - 결제한 기간이 남아 {keep_until.isoformat()}까지 PRO 유지")
            else:
                logger.info(f"[Paddle Webhook] ⬇️ user_id={user.id} → BASIC 다운그레이드")
        else:
            logger.warning(f"[Paddle Webhook] 구독 취소 - subscription_id로 유저 찾기 실패: {subscription_id}")

    elif event_type == "subscription.updated":
        # 구독 상태 변경 (예: paused → active, 갱신으로 결제 기간이 넘어감 등)
        subscription_id = data.get("id")
        status = data.get("status", "")
        user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first() if subscription_id else None
        if user and status == "active":
            resume_subscription(user)
            record_paid_period(user, data)
            db.commit()
            logger.info(f"[Paddle Webhook] ✅ user_id={user.id} → PRO 유지/복원 (결제 기간 끝: {user.paid_until})")

    return {"status": "success"}


async def _fetch_paid_until(subscription_id: str):
    """구독의 마지막 완료 결제가 덮는 기간의 끝. 조회할 수 없으면 None (그러면 예전처럼 바로 BASIC)."""
    api_key = os.getenv("PADDLE_API_KEY", "")
    if not api_key:
        return None
    sandbox = os.getenv("PADDLE_ENVIRONMENT", "").strip().lower() == "sandbox"
    base = "https://sandbox-api.paddle.com" if sandbox else "https://api.paddle.com"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{base}/transactions",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"subscription_id": subscription_id, "status": "completed", "order_by": "created_at[DESC]", "per_page": 1},
            )
            resp.raise_for_status()
            transactions = resp.json().get("data") or []
    except Exception as e:
        logger.warning(f"[Paddle Webhook] 마지막 결제 조회 실패 ({subscription_id}): {e}")
        return None
    return period_end_of(transactions[0]) if transactions else None
