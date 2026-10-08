"""분석 화면: 테스트 상세(측정 구간·시간대별 분포)와, 채널의 "가장 성과 좋은 썸네일"을 VPH로 고르는지."""
import os

os.environ["SENTRY_DSN"] = ""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from models import Base, User, Channel, Video, ABTest, Variation, MetricLog, TestStatus

NOON = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def setup():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    user = User(google_user_id="g1", email="creator@example.com")
    stranger = User(google_user_id="g2", email="other@example.com")
    db.add_all([user, stranger])
    db.commit()
    channel = Channel(user_id=user.id, youtube_channel_id="UC1", channel_title="Mine", oauth_refresh_token="r")
    other_channel = Channel(user_id=stranger.id, youtube_channel_id="UC2", channel_title="Theirs", oauth_refresh_token="r")
    db.add_all([channel, other_channel])
    db.commit()
    video = Video(channel_id=channel.id, youtube_video_id="vid1")
    other_video = Video(channel_id=other_channel.id, youtube_video_id="vid2")
    db.add_all([video, other_video])
    db.commit()
    test = ABTest(video_id=video.id, status=TestStatus.RUNNING, swap_interval_minutes=240,
                  start_time=NOON - timedelta(hours=12), end_time=NOON + timedelta(days=1),
                  last_swapped_at=NOON)
    other_test = ABTest(video_id=other_video.id, status=TestStatus.RUNNING, swap_interval_minutes=240,
                        start_time=NOON, end_time=NOON + timedelta(days=1))
    db.add_all([test, other_test])
    db.commit()
    a = Variation(ab_test_id=test.id, name="Variation A", is_control=True)
    b = Variation(ab_test_id=test.id, name="Variation B")
    db.add_all([a, b])
    db.commit()
    test.current_variation_id = b.id
    # A: 8시간 동안 +80 (VPH 10), 누적은 더 많음 / B: 2시간(10~12시) 동안 +60 (VPH 30)
    db.add_all([
        MetricLog(variation_id=a.id, views_gained=80, hours_exposed=8, measured_at=NOON - timedelta(hours=2)),
        MetricLog(variation_id=b.id, views_gained=60, hours_exposed=2, measured_at=NOON),
    ])
    db.commit()
    # 끝난 테스트 2개: 하나는 C가 원본보다 +50%로 승리, 하나는 원본이 이김
    done_video = Video(channel_id=channel.id, youtube_video_id="vid3")
    kept_video = Video(channel_id=channel.id, youtube_video_id="vid4")
    db.add_all([done_video, kept_video])
    db.commit()
    for vid, end, winner_is_original in ((done_video, NOON - timedelta(days=2), False), (kept_video, NOON - timedelta(days=1), True)):
        finished = ABTest(video_id=vid.id, status=TestStatus.COMPLETED, swap_interval_minutes=240,
                          start_time=end - timedelta(days=1), end_time=end)
        db.add(finished)
        db.commit()
        orig = Variation(ab_test_id=finished.id, name="Variation A", is_control=True, title_text=f"Title {vid.youtube_video_id}",
                         is_winner=winner_is_original)
        cand = Variation(ab_test_id=finished.id, name="Variation C", is_winner=not winner_is_original)
        db.add_all([orig, cand])
        db.commit()
        db.add_all([
            MetricLog(variation_id=orig.id, views_gained=40, hours_exposed=4, measured_at=end - timedelta(hours=4)),  # VPH 10
            MetricLog(variation_id=cand.id, views_gained=60 if not winner_is_original else 20, hours_exposed=4, measured_at=end),
        ])
        db.commit()
    ids = {"test": test.id, "other_test": other_test.id, "a": a.id, "b": b.id}
    token = main.create_access_token(user.id, channel.id)
    db.close()

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    main.app.dependency_overrides[main.get_db] = override_get_db
    client = TestClient(main.app)
    client.cookies.set("auth_token", token)
    yield client, ids
    main.app.dependency_overrides.pop(main.get_db, None)
    engine.dispose()


def test_insights_list_windows_and_spread_views_over_the_hours(setup):
    client, ids = setup
    data = client.get(f"/api/tests/{ids['test']}/insights").json()

    a, b = data["variations"]  # 원본 A가 먼저
    assert a["name"] == "Variation A" and a["vph"] == 10 and a["is_live"] is False
    assert b["is_live"] is True and data["live_since"] == "2026-10-05T12:00:00Z"

    assert b["windows"] == [{"start": "2026-10-05T10:00:00Z", "end": "2026-10-05T12:00:00Z", "hours": 2, "views_gained": 60, "vph": 30}]
    # 10~12시(UTC) 두 칸에 60분씩, 조회수도 시간에 비례해 30씩
    assert b["hourly_minutes"][10] == 60 and b["hourly_minutes"][11] == 60 and sum(b["hourly_minutes"]) == 120
    assert b["hourly_views"][10] == 30 and b["hourly_views"][11] == 30
    # A는 02~10시 8시간, 조회수 합은 그대로 80
    assert sum(a["hourly_minutes"]) == 8 * 60 and round(sum(a["hourly_views"])) == 80


def test_insights_of_another_channels_test_are_not_visible(setup):
    client, ids = setup
    assert client.get(f"/api/tests/{ids['other_test']}/insights").status_code == 404


def test_best_thumbnail_is_chosen_by_views_per_hour(setup):
    client, _ = setup
    best = client.get("/api/analytics").json()["best_variation"]
    # 누적 조회수는 A(80)가 많지만, 시간당 조회수는 B(30)가 높다 - 테스트 승자와 같은 기준
    assert best["name"] == "Variation B" and best["vph"] == 30 and best["total_views_gained"] == 60


def test_analytics_reports_lift_over_the_original_thumbnail(setup):
    client, _ = setup
    data = client.get("/api/analytics").json()

    # 끝난 테스트: 오래된 것부터. 승자 C는 원본(VPH 10)보다 +50%, 다른 테스트는 원본 유지(0%)
    lifts = data["completed_lifts"]
    assert [(x["winner_name"], x["lift_pct"], x["original_won"]) for x in lifts] == [
        ("Variation C", 50.0, False),
        ("Variation A", 0.0, True),
    ]
    assert data["average_lift_pct"] == 25.0

    # 진행 중: B(VPH 30)가 원본 A(VPH 10)보다 +200% 앞서는 중
    assert data["running_leaders"] == [{
        "test_id": data["running_leaders"][0]["test_id"], "title": "vid1",
        "leader_name": "Variation B", "leader_is_original": False, "lift_pct": 200.0, "na_reason": None,
    }]
    assert all(x["na_reason"] is None for x in lifts)


def test_dashboard_tests_carry_a_title_and_the_finished_result(setup):
    client, _ = setup
    tests = {t["video_id"]: t for t in client.get("/api/tests").json()["tests"]}

    # 영상 제목은 저장하지 않으므로 원본 후보의 제목, 없으면 영상 ID를 이름으로 쓴다
    assert tests["vid3"]["title"] == "Title vid3"
    assert tests["vid1"]["title"] == "vid1"

    # 끝난 테스트는 분석 페이지와 같은 원본 대비 상승률을 함께 보낸다
    assert tests["vid3"]["result"]["lift_pct"] == 50.0 and tests["vid3"]["low_sample"] is False
    assert tests["vid4"]["result"]["original_won"] is True
    assert tests["vid1"]["result"] is None  # 진행 중
    assert [v["is_control"] for v in tests["vid3"]["variations"]] == [True, False]


def test_a_finished_test_with_few_views_is_marked_low_sample(setup):
    client, _ = setup
    from models import MetricLog as _M, Variation as _V, ABTest as _T, Video as _Vid
    db = next(main.app.dependency_overrides[main.get_db]())
    test = db.query(_T).join(_Vid).filter(_Vid.youtube_video_id == "vid3").first()
    for log in db.query(_M).join(_V).filter(_V.ab_test_id == test.id):
        log.views_gained = 2  # 테스트 동안 조회수 +4 - 승자가 우연일 수 있다
    db.commit()
    db.close()

    tests = {t["video_id"]: t for t in client.get("/api/tests").json()["tests"]}
    assert tests["vid3"]["total_views_gained"] == 4 and tests["vid3"]["low_sample"] is True


def test_deleted_tests_are_not_counted_in_the_overview(setup):
    client, ids = setup
    data = client.get("/api/analytics").json()
    assert (data["total_tests"], data["completed_tests"], data["active_tests"], data["stopped_tests"]) == (3, 2, 1, 0)

    from models import ABTest as _T
    db = next(main.app.dependency_overrides[main.get_db]())
    deleted = db.get(_T, ids["test"])
    deleted.is_deleted, deleted.status = True, TestStatus.STOPPED  # 사용자가 삭제(취소)한 테스트
    db.commit()
    db.close()

    data = client.get("/api/analytics").json()
    # 화면에서 사라진 테스트는 숫자에서도 빠진다
    assert (data["total_tests"], data["completed_tests"], data["active_tests"], data["stopped_tests"]) == (2, 2, 0, 0)


def test_a_test_whose_original_was_never_measured_is_listed_with_the_reason(setup):
    client, ids = setup
    from models import ABTest as _T, Variation as _V, MetricLog as _M
    db = next(main.app.dependency_overrides[main.get_db]())
    test = db.get(_T, ids["test"])
    test.status = TestStatus.COMPLETED
    db.get(_V, ids["b"]).is_winner = True
    db.query(_M).filter(_M.variation_id == ids["a"]).delete()  # 원본 차례가 오기 전에 끝난 테스트
    db.commit()
    db.close()

    lifts = client.get("/api/analytics").json()["completed_lifts"]
    row = next(x for x in lifts if x["test_id"] == ids["test"])
    # 숨기지 않고, 상승률 대신 이유를 보낸다
    assert row["lift_pct"] is None and row["na_reason"] == "original_not_measured"
