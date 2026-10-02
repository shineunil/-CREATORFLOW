"""
2단계 로그인(개인 구글 계정 로그인 → YouTube 채널 연결), 로그인 순간 계정 언어 저장, 로그인 CSRF 방어 회귀 테스트.
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
EMAIL = "creator@example.com"
CHANNEL_ID = "UC-test-channel"

youtube_calls = []


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
        youtube_calls.append(url)
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
    youtube_calls.clear()
    yield SessionLocal
    main.app.dependency_overrides.pop(main.get_db, None)
    engine.dispose()


@pytest.fixture()
def revoked(monkeypatch):
    tokens = []

    async def fake_revoke(token):
        tokens.append(token)

    monkeypatch.setattr(main, "_revoke_google_token", fake_revoke)
    return tokens


def _query(location):
    return urllib.parse.parse_qs(urllib.parse.urlparse(location).query)


def _start(client, path):
    """/api/auth/login 또는 /api/auth/connect를 거쳐 구글로 보낼 state 값을 돌려준다 (같은 브라우저 쿠키도 client에 남음)."""
    res = client.get(path, follow_redirects=False)
    assert res.status_code in (302, 307)
    return _query(res.headers["location"])["state"][0]


def _start_login(client, query=""):
    return _start(client, f"/api/auth/login{query}")


def _start_connect(client, query=""):
    return _start(client, f"/api/auth/connect{query}")


def _callback(client, state, **headers):
    return client.get(f"/api/auth/callback?code=abc&state={urllib.parse.quote(state)}", headers=headers, follow_redirects=False)


def _exchange(client, location):
    assert client.get(f"/api/auth/exchange?code={_query(location)['auth_code'][0]}").status_code == 200


def _log_in(client):
    location = _callback(client, _start_login(client)).headers["location"]
    _exchange(client, location)
    return location


def _connect(client, query=""):
    location = _callback(client, _start_connect(client, query)).headers["location"]
    if "auth_code=" in location:
        _exchange(client, location)
    return location


def _user(SessionLocal, google_user_id=GOOGLE_ID):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.google_user_id == google_user_id).one()
    finally:
        db.close()


def _channel(SessionLocal, youtube_channel_id):
    db = SessionLocal()
    try:
        return db.query(Channel).filter(Channel.youtube_channel_id == youtube_channel_id).one()
    finally:
        db.close()


def _channel_count(SessionLocal):
    db = SessionLocal()
    try:
        return db.query(Channel).count()
    finally:
        db.close()


# --- 구글로 보내는 주소 ---

def test_login_asks_only_for_the_google_account():
    res = TestClient(main.app).get("/api/auth/login", follow_redirects=False)
    query = _query(res.headers["location"])
    # YouTube 권한을 묻지 않아야 구글이 브랜드 채널이 아닌 개인 구글 계정만 보여준다
    assert query["scope"] == ["openid email profile"]
    assert query["prompt"] == ["select_account"]
    assert "access_type" not in query


def test_connect_asks_for_youtube_and_shows_the_channel_chooser(session_factory):
    client = TestClient(main.app)
    _log_in(client)
    res = client.get("/api/auth/connect", follow_redirects=False)
    query = _query(res.headers["location"])
    assert "https://www.googleapis.com/auth/youtube.force-ssl" in query["scope"][0]
    # 매번 다른 계정·브랜드 채널을 고를 수 있고, 백그라운드 테스트용 refresh_token을 받는다
    assert query["prompt"] == ["consent select_account"]
    assert query["access_type"] == ["offline"]
    # 다시 연결하며 YouTube 체크를 놓쳐도, 예전에 승인한 권한이 토큰에 함께 담겨야 한다
    assert query["include_granted_scopes"] == ["true"]


def test_connect_without_logging_in_goes_to_the_login_page(session_factory):
    res = TestClient(main.app).get("/api/auth/connect", follow_redirects=False)
    assert res.headers["location"].endswith("/login?error=session_expired")


# --- 2단계: 로그인 → 채널 연결 ---

def test_first_login_creates_an_account_without_a_channel(session_factory):
    client = TestClient(main.app)
    location = _log_in(client)

    assert "/connect?auth_code=" in location  # 채널이 없으니 채널 연결 화면으로
    assert youtube_calls == []  # 로그인은 YouTube를 건드리지 않는다
    assert _channel_count(session_factory) == 0
    me = client.get("/api/user/me").json()
    assert me["email"] == EMAIL and me["has_channel"] is False
    # 채널이 필요한 화면은 409로 알려 프론트가 채널 연결 화면으로 보낸다
    res = client.get("/api/videos")
    assert res.status_code == 409 and res.json()["detail"] == "no_channel"


def test_connecting_a_channel_attaches_it_to_the_logged_in_account(session_factory):
    client = TestClient(main.app)
    _log_in(client)
    location = _connect(client)

    assert "/dashboard?auth_code=" in location and "connected_channel=Test%20Channel" in location
    channel = _channel(session_factory, CHANNEL_ID)
    assert channel.user_id == _user(session_factory).id
    assert channel.oauth_refresh_token == "refresh"
    assert client.get("/api/user/me").json()["has_channel"] is True


def test_logging_in_again_opens_the_first_connected_channel(session_factory):
    client = TestClient(main.app)
    _log_in(client)
    _connect(client)

    again = TestClient(main.app)
    location = _log_in(again)
    assert "/dashboard?auth_code=" in location
    assert again.get("/api/user/me").json()["channel_title"] == "Test Channel"


def test_billing_belongs_to_whoever_logged_in(session_factory):
    client = TestClient(main.app)
    _log_in(client)
    # 채널이 없어도 결제는 계정에 붙는다 - 결제 내역이 없어서 404
    assert client.get("/api/billing/portal").status_code == 404


# --- 로그인 순간 계정 언어 ---

def test_callback_saves_the_language_login_started_in(session_factory):
    client = TestClient(main.app)
    state = _start_login(client, "?locale=ko")
    # 브라우저 언어가 영어여도, 사용자가 보던 화면 언어(한국어)가 우선한다
    res = _callback(client, state, **{"Accept-Language": "en-US"})
    assert res.status_code in (302, 307) and "auth_code=" in res.headers["location"]
    assert _user(session_factory).locale == "ko"
    assert any('oauth_locale=""' in c for c in res.headers.get_list("set-cookie"))  # 임시 쿠키 삭제


def test_login_link_remembers_only_supported_locales():
    client = TestClient(main.app)
    res = client.get("/api/auth/login?locale=ko", follow_redirects=False)
    cookies = res.headers.get_list("set-cookie")
    assert any("oauth_locale=ko" in c and "Path=/api/auth" in c for c in cookies)

    res = TestClient(main.app).get("/api/auth/login?locale=xx", follow_redirects=False)
    assert not any("oauth_locale" in c for c in res.headers.get_list("set-cookie"))


@pytest.mark.parametrize("accept_language, expected", [("ko-KR,ko;q=0.9", "ko"), ("en-US,en;q=0.9", "en")])
def test_callback_falls_back_to_browser_language(session_factory, accept_language, expected):
    client = TestClient(main.app)
    _callback(client, _start_login(client), **{"Accept-Language": accept_language})
    assert _user(session_factory).locale == expected


def test_callback_keeps_a_language_the_user_already_chose(session_factory):
    db = session_factory()
    db.add(User(google_user_id=GOOGLE_ID, email=EMAIL, locale="en"))
    db.commit()
    db.close()

    client = TestClient(main.app)
    _callback(client, _start_login(client, "?locale=ko"), **{"Accept-Language": "ko-KR"})
    assert _user(session_factory).locale == "en"


# --- 로그인 CSRF 방어 ---

def test_callback_rejects_a_login_started_in_another_browser(session_factory):
    # 공격자 브라우저에서 만든 구글 로그인 주소(state)를 피해자 브라우저가 열고 돌아온 상황
    attacker_state = _start_login(TestClient(main.app))
    res = _callback(TestClient(main.app), attacker_state)
    assert "error=session_expired" in res.headers["location"]


def test_channel_connect_started_in_another_browser_is_rejected(session_factory):
    # 공격자가 자기 계정으로 만든 "채널 연결" 주소를 피해자가 열어도, 피해자 채널이 공격자 계정에 붙지 않는다
    attacker = TestClient(main.app)
    _log_in(attacker)
    attacker_state = _start_connect(attacker)
    res = _callback(TestClient(main.app), attacker_state)
    assert "error=session_expired" in res.headers["location"]
    assert _channel_count(session_factory) == 0


def test_callback_rejects_a_missing_or_tampered_state(session_factory):
    client = TestClient(main.app)
    state = _start_login(client)
    res = client.get("/api/auth/callback?code=abc", follow_redirects=False)
    assert "error=session_expired" in res.headers["location"]
    res = _callback(client, state + "x")
    assert "error=session_expired" in res.headers["location"]


def test_auth_code_can_only_be_exchanged_by_the_browser_that_logged_in(session_factory):
    client = TestClient(main.app)
    res = _callback(client, _start_login(client))
    auth_code = _query(res.headers["location"])["auth_code"][0]

    # 다른 브라우저가 이 auth_code 주소를 열어도 교환되지 않는다
    assert TestClient(main.app).get(f"/api/auth/exchange?code={auth_code}").status_code == 400

    # 로그인한 브라우저에서는 교환되고, 로그인 쿠키가 Lax로 설정된다
    res = client.get(f"/api/auth/exchange?code={auth_code}")
    assert res.status_code == 200
    auth_cookie = next(c for c in res.headers.get_list("set-cookie") if c.startswith("auth_token="))
    assert "HttpOnly" in auth_cookie and "SameSite=lax" in auth_cookie

    # 한 번 쓴 코드는 다시 쓸 수 없다
    assert client.get(f"/api/auth/exchange?code={auth_code}").status_code == 400


def test_cancelling_the_channel_chooser_returns_to_the_connect_page(session_factory):
    client = TestClient(main.app)
    _log_in(client)
    state = _start_connect(client)
    res = client.get(f"/api/auth/callback?error=access_denied&state={urllib.parse.quote(state)}", follow_redirects=False)
    assert "/connect?error=cancelled" in res.headers["location"]


# --- "다시 연동" 모드 ---

def test_reconnect_rejects_a_different_channel_and_changes_nothing(session_factory, revoked):
    client = TestClient(main.app)
    _log_in(client)
    _connect(client)  # CHANNEL_ID 채널 연결

    # 같은 계정에 연동 해제된 다른 채널이 있고, 그 채널을 다시 연동하려는 상황
    db = session_factory()
    db.add(Channel(user_id=_user(session_factory).id, youtube_channel_id="UC-disconnected", channel_title="Old Channel"))
    db.commit()
    db.close()
    target = _channel(session_factory, "UC-disconnected").id

    location = _connect(client, f"?reconnect={target}")  # 구글 화면에서 다른 채널(CHANNEL_ID)을 고름
    assert "error=reconnect_wrong_channel" in location and "expected=Old%20Channel" in location
    assert "auth_code=" not in location
    assert revoked == ["refresh"]  # 잘못 받은 권한은 돌려준다
    assert _channel(session_factory, "UC-disconnected").oauth_refresh_token is None  # 아무것도 바뀌지 않음


def test_reconnect_succeeds_when_the_same_channel_is_chosen(session_factory):
    client = TestClient(main.app)
    _log_in(client)
    _connect(client)
    target = _channel(session_factory, CHANNEL_ID).id
    assert "auth_code=" in _connect(client, f"?reconnect={target}")


# --- 다른 계정에 붙어 있는 채널 ---

def _logged_in_as_mine(session_factory, their_token, my_plan="PRO", their_google_id="other-google"):
    """구글이 돌려줄 채널(CHANNEL_ID)은 다른 계정(other) 소속, 이 브라우저에 로그인한 사람은 mine."""
    db = session_factory()
    other = User(google_user_id=their_google_id, email="other@example.com")
    mine = User(google_user_id="mine-google", email="mine@example.com", plan=main.PlanType[my_plan])
    db.add_all([other, mine])
    db.commit()
    db.add(Channel(user_id=other.id, youtube_channel_id=CHANNEL_ID, channel_title="Other Channel", oauth_refresh_token=their_token))
    my_channel = Channel(user_id=mine.id, youtube_channel_id="UC-mine", channel_title="Mine")
    db.add(my_channel)
    db.commit()
    client = TestClient(main.app)
    client.cookies.set("auth_token", main.create_access_token(mine.id, my_channel.id))
    ids = {"mine": mine.id, "other": other.id}
    db.close()
    return client, ids


def test_adding_a_channel_owned_by_another_account_is_refused(session_factory, revoked):
    client, ids = _logged_in_as_mine(session_factory, their_token="theirs")
    location = _connect(client)

    assert "/dashboard?error=channel_owned_elsewhere" in location and "auth_code=" not in location
    assert revoked == ["refresh"]
    owned = _channel(session_factory, CHANNEL_ID)
    assert owned.user_id == ids["other"]
    assert owned.oauth_refresh_token == "theirs"  # 남의 채널 권한을 덮어쓰지 않음


def test_refusal_on_a_new_account_is_shown_on_the_connect_page(session_factory, revoked):
    db = session_factory()
    other = User(google_user_id="other-google", email="other@example.com")
    db.add(other)
    db.commit()
    db.add(Channel(user_id=other.id, youtube_channel_id=CHANNEL_ID, channel_title="Other Channel", oauth_refresh_token="theirs"))
    db.commit()
    db.close()

    client = TestClient(main.app)
    _log_in(client)
    # 아직 채널이 없는 계정이라 대시보드가 아닌 채널 연결 화면에서 이유를 보여준다
    assert "/connect?error=channel_owned_elsewhere" in _connect(client)


def test_a_channel_disconnected_from_another_account_moves_to_this_account(session_factory, revoked):
    client, ids = _logged_in_as_mine(session_factory, their_token=None)
    location = _connect(client)

    assert "auth_code=" in location
    owned = _channel(session_factory, CHANNEL_ID)
    assert owned.user_id == ids["mine"]
    assert owned.oauth_refresh_token == "refresh"
    assert revoked == []


def test_a_channel_from_an_account_made_with_the_same_google_identity_moves(session_factory, revoked):
    # 2단계 로그인 전에 이 채널(구글 신원 GOOGLE_ID)로 로그인해 따로 생긴 계정 - 구글 화면에서 그 신원을 고른 사람은
    # 원래 그 계정에도 들어갈 수 있으므로, 연결 중이어도 지금 계정으로 옮긴다
    client, ids = _logged_in_as_mine(session_factory, their_token="theirs", their_google_id=GOOGLE_ID)
    location = _connect(client)

    assert "auth_code=" in location
    assert _channel(session_factory, CHANNEL_ID).user_id == ids["mine"]
    assert revoked == []


def test_moving_a_channel_still_respects_the_channel_limit(session_factory, revoked):
    client, ids = _logged_in_as_mine(session_factory, their_token=None, my_plan="BASIC")
    location = _connect(client)

    assert "error=channel_limit_reached" in location
    assert _channel(session_factory, CHANNEL_ID).user_id == ids["other"]  # 옮기지 않음
    assert revoked == ["refresh"]


def test_login_ignores_a_leftover_session_from_another_account(session_factory):
    # 다른 계정(mine)의 쿠키가 남은 브라우저에서 로그인하면, mine과 상관없는 새 로그인이다
    client, ids = _logged_in_as_mine(session_factory, their_token=None)
    location = _callback(client, _start_login(client)).headers["location"]

    assert "/connect?auth_code=" in location
    assert _user(session_factory).id not in (ids["mine"], ids["other"])
    assert _channel(session_factory, CHANNEL_ID).user_id == ids["other"]
