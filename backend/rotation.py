"""
다음에 걸 후보 고르기 - 각 후보가 하루의 시간대(아침·낮·저녁·밤)를 고르게 나눠 갖게 한다.

예전엔 B -> C -> A 고정 순서였는데, "후보 수 x 교체 간격"이 하루와 맞아떨어지면(예: 후보 2개 x 12시간)
매일 같은 후보가 같은 시간대에만 걸려서, 썸네일이 아니라 낮과 밤을 비교하게 됐다.
이제는 다가오는 구간과 같은 시간대에 지금까지 가장 덜 걸렸던 후보를 고른다.
시간대는 UTC 1시간 단위 24칸으로 센다 - 24칸을 고르게 채우는 것이 목적이라 시청자가 어느 시간대에 있든 똑같이 공정하다.
"""
from datetime import datetime, timedelta, timezone

_HOURS_PER_DAY = 24


def _as_utc(moment: datetime) -> datetime:
    # SQLite 테스트 DB 등에서 시간대 정보가 빠진 값이 오면 UTC로 본다
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def minutes_by_hour(start: datetime, end: datetime) -> list[float]:
    """[start, end) 구간이 하루의 각 시(UTC 0~23시)에 몇 분씩 걸쳐 있는지."""
    buckets = [0.0] * _HOURS_PER_DAY
    start, end = _as_utc(start), _as_utc(end)
    if end <= start:
        return buckets
    whole_days = int((end - start) // timedelta(days=1))
    if whole_days:
        buckets = [60.0 * whole_days] * _HOURS_PER_DAY
        start += timedelta(days=whole_days)
    cursor = start
    while cursor < end:
        next_hour = cursor.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        piece_end = min(next_hour, end)
        buckets[cursor.hour] += (piece_end - cursor).total_seconds() / 60
        cursor = piece_end
    return buckets


def pick_next_variation(variations, current, exposures, now: datetime, window_minutes: int, allow_stay: bool = True):
    """
    variations: 이 테스트의 후보들 (is_control인 원본 A 포함)
    current: 지금 유튜브에 걸려 있는 후보 (첫 교체 전이면 None)
    exposures: 지금까지 각 후보가 걸려 있던 구간 [(variation_id, start, end), ...]
    window_minutes: 다음 교체까지의 간격 - 이번에 고른 후보가 걸려 있을 구간의 길이
    allow_stay: 균형상 지금 후보가 가장 덜 걸렸으면 한 구간 더 유지할지. 후보가 2개면 바꾸기만 해서는
                매일 같은 시간대에 같은 후보가 걸리므로 유지가 필요하다. 사용자가 누른 "지금 교체"는 False.
    """
    if not variations:
        return None
    # 동점일 때의 순서: 새 후보(B, C, ...) 다음 원본(A). 첫 교체는 원본이 이미 걸려 있으니 B부터.
    order = [v for v in variations if not v.is_control] + [v for v in variations if v.is_control]
    if current is None:
        return order[0]

    candidates = [v for v in order if allow_stay or v.id != current.id] or order
    upcoming = minutes_by_hour(now, now + timedelta(minutes=window_minutes))
    by_hour = {v.id: [0.0] * _HOURS_PER_DAY for v in variations}
    for variation_id, start, end in exposures:
        if variation_id not in by_hour:
            continue
        for hour, minutes in enumerate(minutes_by_hour(start, end)):
            by_hour[variation_id][hour] += minutes

    def balance_key(v):
        same_hours = sum(w * m for w, m in zip(upcoming, by_hour[v.id]))
        total = sum(by_hour[v.id])
        # 분 단위 반올림: 부동소수점 오차로 동점이 깨지지 않게
        return (round(same_hours, 3), round(total, 3), order.index(v))

    return min(candidates, key=balance_key)
