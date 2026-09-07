import asyncio
from datetime import datetime, timedelta

import pytest

from models import User, Channel, Video, ABTest, Variation, TestStatus, PlanType
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
        last_swapped_at=last_swapped_at or datetime.utcnow(),
        last_views_snapshot=0,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow() + timedelta(days=1),
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


def test_get_next_variation_cycles_a_b_c_a(engine, db_session):
    test, channel, video, variations = make_running_test(db_session, num_variations=3)

    first = engine._get_next_variation(variations, None)
    assert first.id == variations[0].id

    second = engine._get_next_variation(variations, variations[0])
    assert second.id == variations[1].id

    third = engine._get_next_variation(variations, variations[1])
    assert third.id == variations[2].id

    wraps_around = engine._get_next_variation(variations, variations[2])
    assert wraps_around.id == variations[0].id


def test_first_swap_applies_first_variation_and_sets_swap_count(engine, db_session, monkeypatch):
    test, channel, video, variations = make_running_test(db_session)

    monkeypatch.setattr(scheduler_module, "get_video_views", lambda *a, **k: _async_return(500))
    monkeypatch.setattr(scheduler_module, "update_youtube_thumbnail", lambda *a, **k: _async_return(True))
    monkeypatch.setattr(scheduler_module, "update_youtube_title", lambda *a, **k: _async_return(True))

    run(engine._do_swap(test, db_session))

    assert test.current_variation_id == variations[0].id
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

    logs = variations[0].metric_logs
    assert len(logs) == 1
    assert logs[0].views_gained == 80  # 180 - 100, 스왑 성공 여부와 무관하게 기록됨


def test_warmup_exclusion_narrows_hours_exposed(engine, db_session, monkeypatch):
    test, channel, video, variations = make_running_test(db_session)
    test.current_variation_id = variations[0].id
    test.last_views_snapshot = 0
    now = datetime.utcnow()
    # 워밍업이 이미 캡처된 상태: exposure_start_at이 last_swapped_at보다 30분 늦음
    test.last_swapped_at = now - timedelta(minutes=60)
    test.exposure_start_at = now - timedelta(minutes=30)
    test.warmup_captured = True
    db_session.commit()

    monkeypatch.setattr(scheduler_module, "get_video_views", lambda *a, **k: _async_return(300))
    monkeypatch.setattr(scheduler_module, "update_youtube_thumbnail", lambda *a, **k: _async_return(True))
    monkeypatch.setattr(scheduler_module, "update_youtube_title", lambda *a, **k: _async_return(True))

    run(engine._do_swap(test, db_session))

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


async def _async_return(value):
    return value
