"""/api/videos 영상 목록 캐시와 쿼터 기록 테스트. 유튜브 호출은 가짜로 대신하고, DB는 인메모리 SQLite만 쓴다."""
import os

os.environ["SENTRY_DSN"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from models import Base, User, Channel
from quota_guard import get_today_usage

VIDEOS = [{"id": "vid1", "title": "첫 영상", "thumbnail_url": "https://i.ytimg.com/vi/vid1/hqdefault.jpg"}]


@pytest.fixture()
def setup(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    user = User(google_user_id="g1", email="creator@example.com")
    db.add(user)
    db.commit()
    channel = Channel(user_id=user.id, youtube_channel_id="UC1", channel_title="Test", oauth_refresh_token="refresh")
    db.add(channel)
    db.commit()
    token = main.create_access_token(user.id, channel.id)
    db.close()

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    calls = []

    async def fake_recent_videos(refresh_token):
        calls.append(refresh_token)
        return VIDEOS, 2  # channels.list 1 + playlistItems.list 1

    main.app.dependency_overrides[main.get_db] = override_get_db
    monkeypatch.setattr(main, "get_recent_videos", fake_recent_videos)
    main._video_list_cache.clear()
    client = TestClient(main.app)
    client.cookies.set("auth_token", token)
    yield client, calls, SessionLocal
    main.app.dependency_overrides.pop(main.get_db, None)
    main._video_list_cache.clear()
    engine.dispose()


def _usage(SessionLocal):
    db = SessionLocal()
    try:
        return get_today_usage(db)
    finally:
        db.close()


def test_video_list_is_fetched_once_and_then_served_from_cache(setup):
    client, calls, SessionLocal = setup
    assert client.get("/api/videos").json() == {"videos": VIDEOS}
    assert client.get("/api/videos").json() == {"videos": VIDEOS}
    assert len(calls) == 1  # 두 번째는 유튜브를 다시 부르지 않는다
    assert _usage(SessionLocal) == 2  # 실제 호출한 만큼만 쿼터 사용량에 기록


def test_refresh_bypasses_the_cache(setup):
    client, calls, SessionLocal = setup
    client.get("/api/videos")
    client.get("/api/videos?refresh=true")
    assert len(calls) == 2
    assert _usage(SessionLocal) == 4


def test_an_empty_result_is_not_cached(setup, monkeypatch):
    client, calls, _ = setup

    async def failing_fetch(refresh_token):
        calls.append(refresh_token)
        return [], 1  # 조회 실패와 구분할 수 없으므로 기억하지 않는다

    monkeypatch.setattr(main, "get_recent_videos", failing_fetch)
    client.get("/api/videos")
    client.get("/api/videos")
    assert len(calls) == 2
