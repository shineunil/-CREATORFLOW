"""채널 연동 해제 테스트: 진행 중인 테스트를 원본으로 되돌려 멈추고, 구글 권한을 회수하고, 토큰을 지운다."""
import os

os.environ["SENTRY_DSN"] = ""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from models import Base, User, Channel, Video, ABTest, Variation, TestStatus


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
    video = Video(channel_id=channel.id, youtube_video_id="vid1")
    db.add(video)
    db.commit()
    now = datetime.now(timezone.utc)
    running = ABTest(video_id=video.id, status=TestStatus.RUNNING, swap_interval_minutes=240, start_time=now, end_time=now + timedelta(days=1))
    finished = ABTest(video_id=video.id, status=TestStatus.COMPLETED, swap_interval_minutes=240, start_time=now, end_time=now)
    db.add_all([running, finished])
    db.commit()
    db.add(Variation(ab_test_id=running.id, name="Variation A", title_text="Original", is_control=True))
    db.commit()
    ids = {"channel": channel.id, "running": running.id, "finished": finished.id}
    token = main.create_access_token(user.id, channel.id, True)
    db.close()

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    restored, revoked = [], []

    async def fake_restore(test, db, refresh_token):
        restored.append((test.id, refresh_token))

    async def fake_revoke(refresh_token):
        revoked.append(refresh_token)

    main.app.dependency_overrides[main.get_db] = override_get_db
    monkeypatch.setattr(main, "_restore_original", fake_restore)
    monkeypatch.setattr(main, "_revoke_google_token", fake_revoke)
    client = TestClient(main.app)
    client.cookies.set("auth_token", token)
    yield client, SessionLocal, ids, restored, revoked
    main.app.dependency_overrides.pop(main.get_db, None)
    engine.dispose()


def test_disconnect_restores_and_stops_running_tests_then_revokes(setup):
    client, SessionLocal, ids, restored, revoked = setup
    res = client.post(f"/api/channels/{ids['channel']}/disconnect")
    assert res.status_code == 200 and res.json()["stopped_tests"] == 1

    # 권한이 사라지기 전에, 진행 중인 테스트만 원래 토큰으로 원본 복구
    assert restored == [(ids["running"], "refresh")]
    assert revoked == ["refresh"]

    db = SessionLocal()
    try:
        assert db.get(ABTest, ids["running"]).status == TestStatus.STOPPED
        assert db.get(ABTest, ids["finished"]).status == TestStatus.COMPLETED  # 끝난 테스트는 그대로
        assert db.get(Channel, ids["channel"]).oauth_refresh_token is None
    finally:
        db.close()


def test_me_reports_that_the_channel_is_no_longer_connected(setup):
    client, _, ids, _, _ = setup
    assert client.get("/api/user/me").json()["is_connected"] is True
    client.post(f"/api/channels/{ids['channel']}/disconnect")
    assert client.get("/api/user/me").json()["is_connected"] is False
    # 새 테스트 화면이 "채널 없음"으로 구분할 수 있도록 영상 목록은 400을 준다
    assert client.get("/api/videos").status_code == 400
