from quota_guard import (
    has_quota_for,
    record_usage,
    get_today_usage,
    DAILY_QUOTA_LIMIT,
    QUOTA_SAFETY_MARGIN,
    COST_VIDEOS_LIST,
    COST_THUMBNAILS_SET,
    COST_VIDEOS_UPDATE,
)


def test_fresh_day_has_full_quota(db_session):
    assert get_today_usage(db_session) == 0
    assert has_quota_for(db_session, DAILY_QUOTA_LIMIT - QUOTA_SAFETY_MARGIN) is True


def test_usage_accumulates_across_calls(db_session):
    record_usage(db_session, 50)
    record_usage(db_session, 50)
    assert get_today_usage(db_session) == 100


def test_multiple_record_usage_calls_in_one_uncommitted_session_do_not_conflict(db_session):
    """
    회귀 테스트: _do_swap()은 한 요청 안에서 record_usage()를 최대 3번(조회수 조회,
    썸네일 교체, 제목 교체) 연달아 호출하는데, DB 세션이 autoflush=False라서 flush 없이는
    두 번째 호출이 첫 번째 호출의 미반영(add만 되고 flush 안 된) 행을 못 보고 같은 날짜로
    또 새 행을 만들려다 UNIQUE 제약 위반이 났었다 (라이브에서 실제로 재현됨).
    """
    record_usage(db_session, COST_VIDEOS_LIST)
    record_usage(db_session, COST_THUMBNAILS_SET)
    record_usage(db_session, COST_VIDEOS_UPDATE)

    db_session.commit()  # 실제로 UNIQUE 위반은 커밋(flush) 시점에 드러남

    assert get_today_usage(db_session) == COST_VIDEOS_LIST + COST_THUMBNAILS_SET + COST_VIDEOS_UPDATE


def test_quota_exhausted_blocks_further_usage(db_session):
    record_usage(db_session, DAILY_QUOTA_LIMIT - QUOTA_SAFETY_MARGIN)
    assert has_quota_for(db_session, 1) is False


def test_safety_margin_is_respected_at_the_edge(db_session):
    # 안전 마진 바로 안쪽까지는 허용되어야 함
    record_usage(db_session, DAILY_QUOTA_LIMIT - QUOTA_SAFETY_MARGIN - 100)
    assert has_quota_for(db_session, 100) is True
    assert has_quota_for(db_session, 101) is False
