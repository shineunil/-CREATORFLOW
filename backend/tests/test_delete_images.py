"""테스트 "영구 삭제" 때 Cloudinary 후보 이미지도 지우는지 - 원본은 복구가 확인될 때만, 남이 쓰는 이미지는 남긴다."""
import os

os.environ["SENTRY_DSN"] = ""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
import storage
from models import Base, User, Channel, Video, ABTest, Variation, TestStatus

CLOUD = "https://res.cloudinary.com/demo/image/upload/v1712345678/creatorflow_thumbnails"
ORIGINAL, CAND_B, SHARED = f"{CLOUD}/orig.jpg", f"{CLOUD}/b.png", f"{CLOUD}/shared.jpg"
YOUTUBE = "https://i.ytimg.com/vi/vid1/hqdefault.jpg"


@pytest.fixture()
def setup(monkeypatch):
    monkeypatch.setattr(storage, "CLOUDINARY_CLOUD_NAME", "demo")
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
    other_video = Video(channel_id=channel.id, youtube_video_id="vid2")
    db.add_all([video, other_video])
    db.commit()
    now = datetime.now(timezone.utc)
    test = ABTest(video_id=video.id, status=TestStatus.RUNNING, swap_interval_minutes=240, start_time=now, end_time=now + timedelta(days=1))
    other = ABTest(video_id=other_video.id, status=TestStatus.RUNNING, swap_interval_minutes=240, start_time=now, end_time=now + timedelta(days=1))
    db.add_all([test, other])
    db.commit()
    db.add_all([
        Variation(ab_test_id=test.id, name="Variation A", is_control=True, thumbnail_image_url=ORIGINAL),
        Variation(ab_test_id=test.id, name="Variation B", thumbnail_image_url=CAND_B),
        Variation(ab_test_id=test.id, name="Variation C", thumbnail_image_url=SHARED),
        Variation(ab_test_id=test.id, name="Variation D", thumbnail_image_url=YOUTUBE),
        Variation(ab_test_id=other.id, name="Variation B", thumbnail_image_url=SHARED),  # 다른 테스트도 쓰는 이미지
    ])
    db.commit()
    ids = {"test": test.id}
    token = main.create_access_token(user.id, channel.id)
    db.close()

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    deleted, outcome = [], {"restored": True}

    async def fake_restore(test, db, refresh_token):
        return outcome["restored"]

    async def fake_delete(url):
        deleted.append(url)
        return True

    main.app.dependency_overrides[main.get_db] = override_get_db
    monkeypatch.setattr(main, "_restore_original", fake_restore)
    monkeypatch.setattr(storage, "delete_thumbnail_from_cloud", fake_delete)
    client = TestClient(main.app)
    client.cookies.set("auth_token", token)
    yield client, SessionLocal, ids, deleted, outcome
    main.app.dependency_overrides.pop(main.get_db, None)
    engine.dispose()


def _urls(SessionLocal, test_id):
    db = SessionLocal()
    try:
        return {v.name: v.thumbnail_image_url for v in db.query(Variation).filter(Variation.ab_test_id == test_id)}
    finally:
        db.close()


def test_deleting_a_test_removes_its_images_once_the_original_is_back(setup):
    client, SessionLocal, ids, deleted, _ = setup
    assert client.delete(f"/api/tests/{ids['test']}").status_code == 200

    # 원본 백업과 후보 B는 지우고, 다른 테스트가 쓰는 이미지와 유튜브 주소는 건드리지 않는다
    assert sorted(deleted) == sorted([ORIGINAL, CAND_B])
    urls = _urls(SessionLocal, ids["test"])
    assert urls["Variation A"] is None and urls["Variation B"] is None
    assert urls["Variation C"] == SHARED and urls["Variation D"] == YOUTUBE


def test_the_original_backup_is_kept_when_the_restore_was_not_confirmed(setup):
    client, SessionLocal, ids, deleted, outcome = setup
    outcome["restored"] = False  # 권한이 없거나 유튜브 복구 실패
    assert client.delete(f"/api/tests/{ids['test']}").status_code == 200

    assert deleted == [CAND_B]  # 원본은 남겨야 나중에라도 되돌릴 수 있다
    assert _urls(SessionLocal, ids["test"])["Variation A"] == ORIGINAL


@pytest.mark.parametrize("url, expected", [
    (f"{CLOUD}/abc.jpg", "creatorflow_thumbnails/abc"),
    ("https://res.cloudinary.com/demo/image/upload/creatorflow_thumbnails/abc.png", "creatorflow_thumbnails/abc"),
    ("https://res.cloudinary.com/someone-else/image/upload/v1/x/abc.jpg", None),  # 다른 계정
    (YOUTUBE, None),
    (None, None),
])
def test_cloud_public_id_only_matches_our_own_images(monkeypatch, url, expected):
    monkeypatch.setattr(storage, "CLOUDINARY_CLOUD_NAME", "demo")
    assert storage.cloud_public_id(url) == expected
