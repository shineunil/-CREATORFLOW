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
