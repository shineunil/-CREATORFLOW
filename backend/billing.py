"""
구독 해지 후에도 이미 결제한 기간이 끝날 때까지 PRO를 유지하는 규칙.

Paddle에서 구독을 '즉시 해지'하면 subscription.canceled가 바로 오고, 그때 payload의
current_billing_period는 null이다. 그래서 결제·갱신 웹훅을 받을 때마다 "어디까지 결제됐는지"
(paid_until)를 저장해 두고, 해지 알림이 오면 그 날짜까지는 PRO를 유지(pro_until)한 뒤 내린다.
"""
import logging
from datetime import datetime, timezone

from models import User, PlanType

logger = logging.getLogger(__name__)


def _as_utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def parse_paddle_time(value) -> datetime | None:
    """Paddle의 RFC 3339 시각 문자열("2026-11-08T03:12:45.123456Z")을 UTC datetime으로."""
    if not value or not isinstance(value, str):
        return None
    try:
        return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        logger.warning(f"[Billing] 알 수 없는 시각 형식: {value!r}")
        return None


def period_end_of(data: dict) -> datetime | None:
    """구독 이벤트는 current_billing_period, 결제(transaction) 이벤트는 billing_period에 기간이 들어 있다."""
    period = data.get("current_billing_period") or data.get("billing_period") or {}
    return parse_paddle_time(period.get("ends_at")) if isinstance(period, dict) else None


def record_paid_period(user: User, data: dict) -> None:
    """결제·갱신으로 알게 된 '결제된 기간의 끝'을 저장한다. 더 앞선 날짜로 되돌리지는 않는다 (웹훅 순서가 뒤바뀔 수 있음)."""
    ends_at = period_end_of(data)
    if ends_at and (user.paid_until is None or ends_at > _as_utc(user.paid_until)):
        user.paid_until = ends_at


def end_subscription(user: User, now: datetime) -> datetime | None:
    """
    구독이 해지·일시정지됐을 때. 결제된 기간이 남았으면 그때까지 PRO를 유지하고 그 시각을 돌려준다.
    남은 기간이 없으면 바로 BASIC으로 내리고 None.
    """
    paid_until = _as_utc(user.paid_until) if user.paid_until else None
    if user.plan == PlanType.PRO and paid_until and paid_until > now:
        user.pro_until = paid_until
        return paid_until
    user.plan = PlanType.BASIC
    user.pro_until = None
    return None


def resume_subscription(user: User) -> None:
    """결제가 다시 완료되거나 구독이 다시 활성화되면 예정된 다운그레이드를 취소한다."""
    user.plan = PlanType.PRO
    user.pro_until = None


def expire_if_due(user: User, now: datetime) -> bool:
    """해지 후 유지 기간이 끝났으면 BASIC으로 내린다. 바뀌었으면 True (커밋은 호출하는 쪽에서)."""
    if user.pro_until is None or _as_utc(user.pro_until) > now:
        return False
    user.plan = PlanType.BASIC
    user.pro_until = None
    logger.info(f"[Billing] user_id={user.id} 해지 후 결제 기간 종료 → BASIC")
    return True


def expire_due_plans(session, now: datetime) -> int:
    """유지 기간이 끝난 유저를 모두 BASIC으로 내린다 (스케줄러가 주기적으로 호출)."""
    due = session.query(User).filter(User.pro_until.isnot(None), User.pro_until <= now).all()
    for user in due:
        expire_if_due(user, now)
    if due:
        session.commit()
    return len(due)
