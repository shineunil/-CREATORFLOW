"""
로그인 순간 계정 언어(users.locale) 저장 + 로그인 CSRF 방어 회귀 테스트.
구글 응답은 가짜로 대신하고, DB는 인메모리 SQLite만 쓴다 (라이브 DB에 손대지 않음).
"""
import os

os.environ["SENTRY_DSN"] = ""  # 테스트 중 오류 모니터링으로 이벤트가 나가지 않게

import urllib.parse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from models import Base, User, Channel

GOOGLE_ID = "google-user-1"
EMAIL = "creator@pages.plusgoogle.com"
CHANNEL_ID = "UC-test-channel"


class _FakeResponse:
    def __init__(self, data):
        self.status_code = 200
        self._data = data
        self.text = str(data)

    def json(self):
        return self._data


class _FakeGoogleClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, *args, **kwargs):
        return _FakeResponse({"access_token": "access", "refresh_token": "refresh"})

    async def get(self, url, *args, **kwargs):
        if "userinfo" in url:
            return _FakeResponse({"id": GOOGLE_ID, "email": EMAIL})
        return _FakeResponse({"items": [{"id": CHANNEL_ID, "snippet": {"title": "Test Channel"}}]})


@pytest.fixture()
def session_factory(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[main.get_db] = override_get_db
    monkeypatch.setattr(main.httpx, "AsyncClient", _FakeGoogleClient)
    yield SessionLocal
    main.app.dependency_overrides.pop(main.get_db, None)
    engine.dispose()


def _saved_locale(SessionLocal):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.google_user_id == GOOGLE_ID).one().locale
    finally:
        db.close()


def _start_login(client, query=""):
    """/api/auth/login을 거쳐 구글로 보낼 state 값을 돌려준다 (같은 브라우저 쿠키도 client에 남음)."""
    res = client.get(f"/api/auth/login{query}", follow_redirects=False)
    assert res.status_code in (302, 307)
    return urllib.parse.parse_qs(urllib.parse.urlparse(res.headers["location"]).query)["state"][0]


def _callback(client, state, **headers):
    return client.get(f"/api/auth/callback?code=abc&state={urllib.parse.quote(state)}", headers=headers, follow_redirects=False)


def test_login_always_shows_the_google_account_chooser():
    res = TestClient(main.app).get("/api/auth/login", follow_redirects=False)
    query = urllib.parse.parse_qs(urllib.parse.urlparse(res.headers["location"]).query)
    # 채널 추가 때 브라우저의 현재 계정이 자동 선택되지 않고, 다른 계정·브랜드 채널을 고를 수 있어야 한다
    assert query["prompt"] == ["consent select_account"]
    # 다시 로그인하며 YouTube 체크를 놓쳐도, 예전에 승인한 권한이 토큰에 함께 담겨야 한다
    assert query["include_granted_scopes"] == ["true"]


def test_login_link_remembers_only_supported_locales():
    client = TestClient(main.app)
    res = client.get("/api/auth/login?locale=ko", follow_redirects=False)
    assert res.status_code in (302, 307)
    cookies = res.headers.get_list("set-cookie")
    assert any("oauth_locale=ko" in c and "Path=/api/auth" in c for c in cookies)

    res = TestClient(main.app).get("/api/auth/login?locale=xx", follow_redirects=False)
    assert not any("oauth_locale" in c for c in res.headers.get_list("set-cookie"))


def test_callback_saves_the_language_login_started_in(session_factory):
    client = TestClient(main.app)
    state = _start_login(client, "?locale=ko")
    # 브라우저 언어가 영어여도, 사용자가 보던 화면 언어(한국어)가 우선한다
    res = _callback(client, state, **{"Accept-Language": "en-US"})
    assert res.status_code in (302, 307) and "auth_code=" in res.headers["location"]
    assert _saved_locale(session_factory) == "ko"
    assert any('oauth_locale=""' in c for c in res.headers.get_list("set-cookie"))  # 임시 쿠키 삭제


@pytest.mark.parametrize("accept_language, expected", [("ko-KR,ko;q=0.9", "ko"), ("en-US,en;q=0.9", "en")])
def test_callback_falls_back_to_browser_language(session_factory, accept_language, expected):
    client = TestClient(main.app)
    state = _start_login(client)
    _callback(client, state, **{"Accept-Language": accept_language})
    assert _saved_locale(session_factory) == expected


def test_callback_keeps_a_language_the_user_already_chose(session_factory):
    db = session_factory()
    db.add(User(google_user_id=GOOGLE_ID, email=EMAIL, locale="en"))
    db.commit()
    db.close()

    client = TestClient(main.app)
    state = _start_login(client, "?locale=ko")
    _callback(client, state, **{"Accept-Language": "ko-KR"})
    assert _saved_locale(session_factory) == "en"


# --- 로그인 CSRF 방어 ---

def _channel_count(SessionLocal):
    db = SessionLocal()
    try:
        return db.query(Channel).count()
    finally:
        db.close()


def test_callback_rejects_a_login_started_in_another_browser(session_factory):
    # 공격자 브라우저에서 만든 구글 로그인 주소(state)를 피해자 브라우저가 열고 돌아온 상황
    attacker_state = _start_login(TestClient(main.app))
    victim = TestClient(main.app)
    res = _callback(victim, attacker_state)
    assert res.status_code in (302, 307)
    assert "error=session_expired" in res.headers["location"]
    assert _channel_count(session_factory) == 0  # 채널이 누구에게도 연결되지 않음


def test_callback_rejects_a_missing_or_tampered_state(session_factory):
    client = TestClient(main.app)
    state = _start_login(client)
    res = client.get("/api/auth/callback?code=abc", follow_redirects=False)
    assert "error=session_expired" in res.headers["location"]
    res = _callback(client, state + "x")
    assert "error=session_expired" in res.headers["location"]
    assert _channel_count(session_factory) == 0


def test_auth_code_can_only_be_exchanged_by_the_browser_that_logged_in(session_factory):
    client = TestClient(main.app)
    state = _start_login(client)
    res = _callback(client, state)
    auth_code = urllib.parse.parse_qs(urllib.parse.urlparse(res.headers["location"]).query)["auth_code"][0]

    # 다른 브라우저가 이 auth_code 주소를 열어도 교환되지 않는다
    other = TestClient(main.app)
    assert other.get(f"/api/auth/exchange?code={auth_code}").status_code == 400

    # 로그인한 브라우저에서는 교환되고, 로그인 쿠키가 Lax로 설정된다
    res = client.get(f"/api/auth/exchange?code={auth_code}")
    assert res.status_code == 200
    auth_cookie = next(c for c in res.headers.get_list("set-cookie") if c.startswith("auth_token="))
    assert "HttpOnly" in auth_cookie and "SameSite=lax" in auth_cookie

    # 한 번 쓴 코드는 다시 쓸 수 없다
    assert client.get(f"/api/auth/exchange?code={auth_code}").status_code == 400


# --- 결제 관리는 계정 주인만 ---

def _log_in(client):
    state = _start_login(client)
    res = _callback(client, state)
    auth_code = urllib.parse.parse_qs(urllib.parse.urlparse(res.headers["location"]).query)["auth_code"][0]
    assert client.get(f"/api/auth/exchange?code={auth_code}").status_code == 200


# --- "다시 연동" 모드 ---

def _channel_id(SessionLocal, youtube_channel_id):
    db = SessionLocal()
    try:
        return db.query(Channel).filter(Channel.youtube_channel_id == youtube_channel_id).one().id
    finally:
        db.close()


def test_reconnect_rejects_a_different_channel_and_changes_nothing(session_factory, monkeypatch):
    revoked = []

    async def fake_revoke(token):
        revoked.append(token)

    monkeypatch.setattr(main, "_revoke_google_token", fake_revoke)
    client = TestClient(main.app)
    _log_in(client)  # CHANNEL_ID 채널로 가입

    # 같은 계정에 연동 해제된 다른 채널이 있고, 그 채널을 다시 연동하려는 상황
    db = session_factory()
    user = db.query(User).filter(User.google_user_id == GOOGLE_ID).one()
    db.add(Channel(user_id=user.id, youtube_channel_id="UC-disconnected", channel_title="Old Channel"))
    db.commit()
    db.close()
    target = _channel_id(session_factory, "UC-disconnected")

    state = _start_login(client, f"?reconnect={target}")
    res = _callback(client, state)  # 구글 화면에서 다른 채널(CHANNEL_ID)을 고름
    location = res.headers["location"]
    assert "error=reconnect_wrong_channel" in location and "expected=Old%20Channel" in location
    assert "auth_code=" not in location
    assert revoked == ["refresh"]  # 잘못 받은 권한은 돌려준다

    db = session_factory()
    try:
        assert db.get(Channel, target).oauth_refresh_token is None  # 아무것도 바뀌지 않음
    finally:
        db.close()


@pytest.fixture()
def revoked(monkeypatch):
    tokens = []

    async def fake_revoke(token):
        tokens.append(token)

    monkeypatch.setattr(main, "_revoke_google_token", fake_revoke)
    return tokens


def _logged_in_as_mine(session_factory, their_token, my_plan="PRO"):
    """구글이 돌려줄 채널(CHANNEL_ID)은 다른 계정(other) 소속, 이 브라우저에 로그인한 사람은 mine."""
    db = session_factory()
    other = User(google_user_id="other-google", email="other@example.com")
    mine = User(google_user_id="mine-google", email="mine@example.com", plan=main.PlanType[my_plan])
    db.add_all([other, mine])
    db.commit()
    db.add(Channel(user_id=other.id, youtube_channel_id=CHANNEL_ID, channel_title="Other Channel", oauth_refresh_token=their_token))
    my_channel = Channel(user_id=mine.id, youtube_channel_id="UC-mine", channel_title="Mine")
    db.add(my_channel)
    db.commit()
    client = TestClient(main.app)
    client.cookies.set("auth_token", main.create_access_token(mine.id, my_channel.id, True))
    ids = {"mine": mine.id, "other": other.id}
    db.close()
    return client, ids


def _owner_of(session_factory, youtube_channel_id):
    db = session_factory()
    try:
        return db.query(Channel).filter(Channel.youtube_channel_id == youtube_channel_id).one()
    finally:
        db.close()


def test_adding_a_channel_owned_by_another_account_is_refused(session_factory, revoked):
    client, ids = _logged_in_as_mine(session_factory, their_token="theirs")
    location = _callback(client, _start_login(client, "?link=true")).headers["location"]

    assert "error=channel_owned_elsewhere" in location and "auth_code=" not in location  # 다른 계정으로 넘어가지 않음
    assert revoked == ["refresh"]
    owned = _owner_of(session_factory, CHANNEL_ID)
    assert owned.user_id == ids["other"]
    assert owned.oauth_refresh_token == "theirs"  # 남의 채널 권한을 덮어쓰지 않음


def test_a_channel_disconnected_from_another_account_moves_to_this_account(session_factory, revoked):
    client, ids = _logged_in_as_mine(session_factory, their_token=None)
    location = _callback(client, _start_login(client, "?link=true")).headers["location"]

    assert "auth_code=" in location
    owned = _owner_of(session_factory, CHANNEL_ID)
    assert owned.user_id == ids["mine"]
    assert owned.oauth_refresh_token == "refresh"
    assert revoked == []


def test_moving_a_disconnected_channel_still_respects_the_channel_limit(session_factory, revoked):
    client, ids = _logged_in_as_mine(session_factory, their_token=None, my_plan="BASIC")
    location = _callback(client, _start_login(client, "?link=true")).headers["location"]

    assert "error=channel_limit_reached" in location
    assert _owner_of(session_factory, CHANNEL_ID).user_id == ids["other"]  # 옮기지 않음
    assert revoked == ["refresh"]


def test_login_button_ignores_a_leftover_session_from_another_account(session_factory, revoked):
    # 다른 계정(mine)의 쿠키가 남은 브라우저에서 "로그인"을 누르면, mine에 채널 추가가 아니라 일반 로그인이다
    client, ids = _logged_in_as_mine(session_factory, their_token=None)
    location = _callback(client, _start_login(client)).headers["location"]

    assert "auth_code=" in location
    assert _owner_of(session_factory, CHANNEL_ID).user_id != ids["mine"]


def test_reconnect_succeeds_when_the_same_channel_is_chosen(session_factory):
    client = TestClient(main.app)
    _log_in(client)
    target = _channel_id(session_factory, CHANNEL_ID)

    state = _start_login(client, f"?reconnect={target}")
    res = _callback(client, state)
    assert "auth_code=" in res.headers["location"]


def test_owner_session_passes_the_billing_owner_check(session_factory):
    client = TestClient(main.app)
    _log_in(client)
    res = client.get("/api/billing/portal")
    # 주인 확인은 통과하고, 결제 내역이 없어서 404가 난다
    assert res.status_code == 404


def test_billing_portal_uses_a_paddle_portal_session(session_factory, monkeypatch):
    client = TestClient(main.app)
    _log_in(client)
    db = session_factory()
    user = db.query(User).filter(User.google_user_id == GOOGLE_ID).one()
    user.stripe_customer_id = "ctm_test"
    user.stripe_subscription_id = "sub_test"
    db.commit()
    db.close()

    sent = {}

    class FakePaddle:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            sent["url"], sent["json"] = url, json
            return main._httpx.Response(
                201,
                json={"data": {"urls": {"general": {"overview": "https://customer-portal.paddle.com/cpl_abc"}}}},
                request=main._httpx.Request("POST", url),
            )

    monkeypatch.setattr(main._httpx, "AsyncClient", FakePaddle)
    res = client.get("/api/billing/portal")
    assert res.status_code == 200
    assert res.json() == {"url": "https://customer-portal.paddle.com/cpl_abc"}
    assert sent["url"].endswith("/customers/ctm_test/portal-sessions")
    assert sent["json"] == {"subscription_ids": ["sub_test"]}


def test_channel_manager_session_cannot_open_billing(session_factory):
    # 채널 주인은 다른 구글 계정으로 가입해 두었고, 관리자가 같은 채널을 골라 로그인한 상황
    db = session_factory()
    owner = User(google_user_id="owner-google-id", email="owner@example.com")
    db.add(owner)
    db.commit()
    db.add(Channel(user_id=owner.id, youtube_channel_id=CHANNEL_ID, channel_title="Test Channel"))
    db.add(Channel(user_id=owner.id, youtube_channel_id="UC-other", channel_title="Other"))
    db.commit()
    other_channel_id = db.query(Channel).filter(Channel.youtube_channel_id == "UC-other").one().id
    db.close()

    client = TestClient(main.app)
    _log_in(client)
    assert client.get("/api/billing/portal").status_code == 403

    # 채널을 바꿔도 주인 권한이 생기지 않는다
    assert client.post(f"/api/channels/{other_channel_id}/switch").status_code == 200
    assert client.get("/api/billing/portal").status_code == 403
