"""
로그인 순간 계정 언어(users.locale) 저장 회귀 테스트.
구글 응답은 가짜로 대신하고, DB는 인메모리 SQLite만 쓴다 (라이브 DB에 손대지 않음).
"""
import os

os.environ["SENTRY_DSN"] = ""  # 테스트 중 오류 모니터링으로 이벤트가 나가지 않게

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from models import Base, User

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


def test_login_link_remembers_only_supported_locales():
    client = TestClient(main.app)
    res = client.get("/api/auth/login?locale=ko", follow_redirects=False)
    assert res.status_code in (302, 307)
    cookie = res.headers.get("set-cookie", "")
    assert "oauth_locale=ko" in cookie and "Path=/api/auth" in cookie

    res = TestClient(main.app).get("/api/auth/login?locale=xx", follow_redirects=False)
    assert "oauth_locale" not in res.headers.get("set-cookie", "")


def test_callback_saves_the_language_login_started_in(session_factory):
    client = TestClient(main.app)
    client.get("/api/auth/login?locale=ko", follow_redirects=False)
    # 브라우저 언어가 영어여도, 사용자가 보던 화면 언어(한국어)가 우선한다
    res = client.get("/api/auth/callback?code=abc", headers={"Accept-Language": "en-US"}, follow_redirects=False)
    assert res.status_code in (302, 307) and "auth_code=" in res.headers["location"]
    assert _saved_locale(session_factory) == "ko"
    assert 'oauth_locale=""' in res.headers.get("set-cookie", "")  # 임시 쿠키 삭제


@pytest.mark.parametrize("accept_language, expected", [("ko-KR,ko;q=0.9", "ko"), ("en-US,en;q=0.9", "en")])
def test_callback_falls_back_to_browser_language(session_factory, accept_language, expected):
    client = TestClient(main.app)
    client.get("/api/auth/callback?code=abc", headers={"Accept-Language": accept_language}, follow_redirects=False)
    assert _saved_locale(session_factory) == expected


def test_callback_keeps_a_language_the_user_already_chose(session_factory):
    db = session_factory()
    db.add(User(google_user_id=GOOGLE_ID, email=EMAIL, locale="en"))
    db.commit()
    db.close()

    client = TestClient(main.app)
    client.get("/api/auth/login?locale=ko", follow_redirects=False)
    client.get("/api/auth/callback?code=abc", headers={"Accept-Language": "ko-KR"}, follow_redirects=False)
    assert _saved_locale(session_factory) == "en"
