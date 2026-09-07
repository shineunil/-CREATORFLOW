import os
from datetime import datetime
from zoneinfo import ZoneInfo

from models import ApiQuotaUsage

# YouTube Data API v3 기본 일일 쿼터는 10,000 유닛 (구글 클라우드 콘솔에서 조정 가능)이며,
# 태평양 시간(PT) 자정에 리셋된다.
# 출처: https://developers.google.com/youtube/v3/determine_quota_cost
DAILY_QUOTA_LIMIT = int(os.getenv("YOUTUBE_DAILY_QUOTA_LIMIT", "10000"))
# 다른 용도(신규 유저 온보딩 등)의 여유분을 남겨두기 위한 안전 마진
QUOTA_SAFETY_MARGIN = int(os.getenv("YOUTUBE_QUOTA_SAFETY_MARGIN", "500"))

COST_VIDEOS_LIST = 1       # get_video_views
COST_VIDEOS_UPDATE = 50    # update_youtube_title
COST_THUMBNAILS_SET = 50   # update_youtube_thumbnail


def _today_pacific() -> str:
    """YouTube 쿼터는 태평양 시간(PT) 자정에 리셋되므로, 그 기준으로 '오늘'을 판단한다."""
    return datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")


def get_today_usage(session) -> int:
    row = session.query(ApiQuotaUsage).filter(ApiQuotaUsage.date == _today_pacific()).first()
    return row.units_used if row else 0


def record_usage(session, units: int):
    """
    실제 YouTube API 호출을 시도한 직후(성공/실패 무관) 호출해 사용량을 누적 기록한다.

    한 요청(예: _do_swap) 안에서도 조회수 조회/썸네일 교체/제목 교체 등으로 여러 번
    호출될 수 있다. DB 세션이 autoflush=False라서, flush 없이는 방금 add()한
    "오늘" 행이 다음 호출의 쿼리에 아직 안 보여서 같은 date로 또 INSERT를 시도하다
    UNIQUE 제약 위반이 났었다 (실제로 라이브에서 재현된 버그). 매번 flush로
    같은 세션 안에서도 즉시 반영되게 해 이 경합을 없앤다.
    """
    today = _today_pacific()
    row = session.query(ApiQuotaUsage).filter(ApiQuotaUsage.date == today).first()
    if row:
        row.units_used += units
    else:
        session.add(ApiQuotaUsage(date=today, units_used=units))
    session.flush()


def has_quota_for(session, units: int) -> bool:
    """안전 마진을 제외하고 요청한 유닛만큼의 쿼터가 남아있는지 확인한다."""
    return (get_today_usage(session) + units) <= (DAILY_QUOTA_LIMIT - QUOTA_SAFETY_MARGIN)
