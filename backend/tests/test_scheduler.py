import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from models import User, Channel, Video, ABTest, Variation, TestStatus, PlanType, MetricLog
from scheduler import AVSchedulerEngine
from youtube_api import TokenRevokedError
import scheduler as scheduler_module


def run(coro):
    return asyncio.run(coro)


def make_running_test(session, num_variations=2, swap_interval_minutes=60, last_swapped_at=None):
    user = User(email="tester@example.com", plan=PlanType.BASIC)
    session.add(user)
    session.commit()

    channel = Channel(user_id=user.id, youtube_channel_id="UC_test", channel_title="Test Channel", oauth_refresh_token="fake-refresh-token")
    session.add(channel)
    session.commit()

    video = Video(channel_id=channel.id, youtube_video_id="vid123")
    session.add(video)
    session.commit()

    test = ABTest(
        video_id=video.id,
        status=TestStatus.RUNNING,
        swap_interval_minutes=swap_interval_minutes,
        last_swapped_at=last_swapped_at or datetime.now(timezone.utc),
        last_views_snapshot=0,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + timedelta(days=1),
    )
    session.add(test)
    session.commit()

    variations = []
    for i in range(num_variations):
        var = Variation(ab_test_id=test.id, name=f"Variation {chr(65+i)}", title_text=f"Title {i}", is_control=(i == 0))
        session.add(var)
        variations.append(var)
    session.commit()

    return test, channel, video, variations


@pytest.fixture()
def engine():
    return AVSchedulerEngine(db_session_maker=lambda: None)  # 실제로 세션을 만들지 않음 (테스트에서 직접 세션을 넘기므로)


def test_get_next_variation_cycles_b_c_a_b(engine, db_session):
    test, channel, video, variations = make_running_test(db_session, num_variations=3)

    # 원본(A)은 이미 유튜브에 적용된 상태라 첫 교체는 B부터
    first = engine._get_next_variation(variations, None)
    assert first.id == variations[1].id

    second = engine._get_next_variation(variations, variations[1])
    assert second.id == variations[2].id

    wraps_around = engine._get_next_variation(variations, variations[2])
    assert wraps_around.id == variations[0].id

    back_to_b = engine._get_next_variation(variations, variations[0])
    assert back_to_b.id == variations[1].id


def test_first_swap_applies_first_new_variation_and_sets_swap_count(engine, db_session, monkeypatch):
    test, channel, video, variations = make_running_test(db_session)

    monkeypatch.setattr(scheduler_module, "get_video_views", lambda *a, **k: _async_return(500))
    monkeypatch.setattr(scheduler_module, "update_youtube_thumbnail", lambda *a, **k: _async_return(True))
    monkeypatch.setattr(scheduler_module, "update_youtube_title", lambda *a, **k: _async_return(True))

    run(engine._do_swap(test, db_session))

    assert test.current_variation_id == variations[1].id  # 원본(A)을 건너뛰고 B 적용
    assert test.swap_count == 1
    assert test.swap_failed is False
    assert test.warmup_captured is False  # 새로 적용된 변인의 워밍업 재캡처 대기 상태
    assert test.last_views_snapshot == 500


def test_failed_swap_keeps_previous_variation_and_sets_swap_failed(engine, db_session, monkeypatch):
    test, channel, video, variations = make_running_test(db_session)
    test.current_variation_id = variations[0].id
    test.swap_count = 1
    db_session.commit()

    monkeypatch.setattr(scheduler_module, "get_video_views", lambda *a, **k: _async_return(1000))
    monkeypatch.setattr(scheduler_module, "update_youtube_thumbnail", lambda *a, **k: _async_return(True))
    # 제목 업데이트가 실패하는 상황을 시뮬레이션
    monkeypatch.setattr(scheduler_module, "update_youtube_title", lambda *a, **k: _async_return(False))

    run(engine._do_swap(test, db_session))

    # 실패했으므로 변인이 그대로 유지되어야 함 (엉뚱한 변인 점수로 기록되는 것 방지)
    assert test.current_variation_id == variations[0].id
    assert test.swap_failed is True
    assert test.swap_count == 1  # 증가하지 않음


def test_swap_records_metric_log_regardless_of_swap_outcome(engine, db_session, monkeypatch):
    test, channel, video, variations = make_running_test(db_session)
    test.current_variation_id = variations[0].id
    test.last_views_snapshot = 100
    db_session.commit()

    monkeypatch.setattr(scheduler_module, "get_video_views", lambda *a, **k: _async_return(180))
    monkeypatch.setattr(scheduler_module, "update_youtube_thumbnail", lambda *a, **k: _async_return(True))
    monkeypatch.setattr(scheduler_module, "update_youtube_title", lambda *a, **k: _async_return(False))  # 스왑은 실패

    run(engine._do_swap(test, db_session))
    db_session.commit()  # 실제 스케줄러도 _do_swap 뒤에 커밋한다 (세션이 autoflush=False라 커밋 전엔 조회되지 않음)

    logs = variations[0].metric_logs
    assert len(logs) == 1
    assert logs[0].views_gained == 80  # 180 - 100, 스왑 성공 여부와 무관하게 기록됨


def test_warmup_exclusion_narrows_hours_exposed(engine, db_session, monkeypatch):
    test, channel, video, variations = make_running_test(db_session)
    test.current_variation_id = variations[0].id
    test.last_views_snapshot = 0
    now = datetime.now(timezone.utc)
    # 워밍업이 이미 캡처된 상태: exposure_start_at이 last_swapped_at보다 30분 늦음
    test.last_swapped_at = now - timedelta(minutes=60)
    test.exposure_start_at = now - timedelta(minutes=30)
    test.warmup_captured = True
    db_session.commit()

    monkeypatch.setattr(scheduler_module, "get_video_views", lambda *a, **k: _async_return(300))
    monkeypatch.setattr(scheduler_module, "update_youtube_thumbnail", lambda *a, **k: _async_return(True))
    monkeypatch.setattr(scheduler_module, "update_youtube_title", lambda *a, **k: _async_return(True))

    run(engine._do_swap(test, db_session))
    db_session.commit()

    logs = variations[0].metric_logs
    assert len(logs) == 1
    # exposure_start_at(30분 전) 기준이어야 하며, last_swapped_at(60분 전) 기준이면 안 됨
    assert 0.4 < logs[0].hours_exposed < 0.6  # 약 0.5h (30분)


def test_token_revoked_marks_channel_needs_reconnect(engine, db_session, monkeypatch):
    test, channel, video, variations = make_running_test(db_session)

    async def raise_revoked(*a, **k):
        raise TokenRevokedError("refresh token invalid")

    monkeypatch.setattr(scheduler_module, "get_video_views", raise_revoked)

    run(engine._do_swap(test, db_session))

    assert channel.needs_reconnect is True
    # current_variation_id는 건드리지 않아야 함 (측정도 스왑도 진행되지 않았으므로)
    assert test.current_variation_id is None


YT_ORIGINAL = "https://i.ytimg.com/vi/vid123/hqdefault.jpg"
KEPT_ORIGINAL = "https://res.cloudinary.com/demo/image/upload/original_vid123.jpg"


def _stub_youtube(monkeypatch, calls):
    monkeypatch.setattr(scheduler_module, "get_video_views", lambda *a, **k: _async_return(500))

    async def fake_thumbnail(*a, **k):
        calls.append("thumbnail")
        return True

    async def fake_title(*a, **k):
        calls.append("title")
        return True

    monkeypatch.setattr(scheduler_module, "update_youtube_thumbnail", fake_thumbnail)
    monkeypatch.setattr(scheduler_module, "update_youtube_title", fake_title)


def test_first_swap_keeps_the_original_thumbnail_before_applying_b(engine, db_session, monkeypatch):
    test, channel, video, variations = make_running_test(db_session)
    variations[0].thumbnail_image_url = YT_ORIGINAL  # 원본(A)은 유튜브 주소로 들어온다
    db_session.commit()

    kept_for = []

    async def fake_snapshot(video_id):
        kept_for.append(video_id)
        return KEPT_ORIGINAL

    monkeypatch.setattr(scheduler_module, "snapshot_original_thumbnail", fake_snapshot)
    calls = []
    _stub_youtube(monkeypatch, calls)

    run(engine._do_swap(test, db_session))

    assert kept_for == ["vid123"]
    assert variations[0].thumbnail_image_url == KEPT_ORIGINAL  # 이후 A 교체·복구는 보관한 원본을 쓴다
    assert test.current_variation_id == variations[1].id


def test_first_swap_waits_when_the_original_cannot_be_kept(engine, db_session, monkeypatch):
    test, channel, video, variations = make_running_test(db_session)
    variations[0].thumbnail_image_url = YT_ORIGINAL
    db_session.commit()

    monkeypatch.setattr(scheduler_module, "snapshot_original_thumbnail", lambda video_id: _async_return(None))
    calls = []
    _stub_youtube(monkeypatch, calls)

    run(engine._do_swap(test, db_session))

    # 원본을 잃지 않도록 B를 걸지 않고, 다음 주기에 다시 시도한다
    assert calls == []
    assert test.current_variation_id is None
    assert test.swap_failed is True
    assert variations[0].thumbnail_image_url == YT_ORIGINAL


def test_later_swaps_do_not_fetch_the_original_again(engine, db_session, monkeypatch):
    test, channel, video, variations = make_running_test(db_session, num_variations=3)  # B 다음은 C (네트워크 없음)
    variations[0].thumbnail_image_url = YT_ORIGINAL  # (보관 이전 데이터라도) 이미 교체가 시작된 테스트
    test.current_variation_id = variations[1].id
    test.swap_count = 1
    db_session.commit()

    async def must_not_run(video_id):
        raise AssertionError("첫 교체 이후에는 원본을 다시 받으면 안 된다 (이미 바뀐 썸네일이 받아짐)")

    monkeypatch.setattr(scheduler_module, "snapshot_original_thumbnail", must_not_run)
    calls = []
    _stub_youtube(monkeypatch, calls)

    run(engine._do_swap(test, db_session))
    assert test.current_variation_id == variations[2].id


# --- 제목이 같으면 제목 교체를 건너뛴다 (쿼터 절약) ---

def test_thumbnail_only_swap_skips_the_title_update_and_its_quota(engine, db_session, monkeypatch):
    from quota_guard import get_today_usage

    test, channel, video, variations = make_running_test(db_session)
    for v in variations:
        v.title_text = "원래 영상 제목"  # 제목 칸을 비워 두면 모든 후보가 원래 제목을 갖는다
    variations[1].thumbnail_image_url = None  # 썸네일 다운로드(네트워크) 없이 확인
    db_session.commit()
    calls = []
    _stub_youtube(monkeypatch, calls)

    run(engine._do_swap(test, db_session))

    assert calls == []  # 제목이 같으니 유튜브 제목 수정 요청을 보내지 않음
    assert test.current_variation_id == variations[1].id  # 교체 자체는 성공 처리
    assert get_today_usage(db_session) == 1  # 조회수 확인 1만 예약 (이전엔 101)


def test_a_different_title_is_still_applied(engine, db_session, monkeypatch):
    test, channel, video, variations = make_running_test(db_session)  # "Title 0" -> "Title 1"
    calls = []
    _stub_youtube(monkeypatch, calls)

    run(engine._do_swap(test, db_session))
    assert calls == ["title"]


def test_winner_that_is_already_live_is_not_uploaded_again(engine, db_session, monkeypatch):
    test, channel, video, variations = make_running_test(db_session)
    for v in variations:
        v.thumbnail_image_url = KEPT_ORIGINAL
    test.current_variation_id = variations[1].id  # B가 지금 걸려 있음
    test.end_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    test.extension_count = 99  # 표본 부족으로 자동 연장되지 않게
    db_session.commit()
    db_session.add(MetricLog(variation_id=variations[1].id, views_gained=500, hours_exposed=1))
    db_session.commit()
    calls = []
    _stub_youtube(monkeypatch, calls)

    run(engine._process_single_test(test, db_session))

    assert test.status == TestStatus.COMPLETED
    assert variations[1].is_winner is True
    assert calls == []  # 승자 B가 이미 걸려 있으니 썸네일·제목을 다시 올리지 않음


async def _async_return(value):
    return value
