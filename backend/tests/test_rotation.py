"""시간대 균형 후보 선택(rotation.py) - 며칠 동안 스케줄러가 교체하는 상황을 그대로 흉내 내어 확인한다."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from rotation import minutes_by_hour, pick_next_variation


@dataclass(frozen=True)
class Var:
    id: int
    is_control: bool = False


A, B, C = Var(1, is_control=True), Var(2), Var(3)
MIDNIGHT = datetime(2026, 10, 5, tzinfo=timezone.utc)


def simulate(variations, interval_hours, days):
    """원본 A가 걸린 상태에서 시작해 interval_hours마다 다음 후보를 고른다. 후보별 시간대(UTC 시)별 노출 분을 돌려준다."""
    exposures, now, current = [], MIDNIGHT, None
    current = pick_next_variation(variations, None, exposures, now, interval_hours * 60)  # 첫 교체
    started = now
    while now < MIDNIGHT + timedelta(days=days):
        now += timedelta(hours=interval_hours)
        exposures.append((current.id, started, now))
        nxt = pick_next_variation(variations, current, exposures, now, interval_hours * 60)
        if nxt.id != current.id:
            current = nxt
        started = now
    totals = {v.id: [0.0] * 24 for v in variations}
    for var_id, start, end in exposures:
        for hour, minutes in enumerate(minutes_by_hour(start, end)):
            totals[var_id][hour] += minutes
    return totals


def test_two_candidates_every_12_hours_share_day_and_night():
    # 예전 고정 순서에서는 B가 매일 0~12시, A가 매일 12~24시만 맡았다
    totals = simulate([A, B], interval_hours=12, days=10)
    for var_id in (A.id, B.id):
        day, night = sum(totals[var_id][:12]), sum(totals[var_id][12:])
        assert abs(day - night) <= 12 * 60  # 많아야 한 구간 차이
    assert abs(sum(totals[A.id][:12]) - sum(totals[B.id][:12])) <= 12 * 60


def test_three_candidates_every_4_hours_cover_every_time_of_day():
    # 예전 고정 순서에서는 각 후보가 매일 같은 4시간대 두 곳만 맡았다
    totals = simulate([A, B, C], interval_hours=4, days=12)
    for var_id in (A.id, B.id, C.id):
        blocks = [sum(totals[var_id][h:h + 4]) for h in range(0, 24, 4)]
        assert min(blocks) > 0  # 모든 4시간대에 한 번 이상 걸림
        assert max(blocks) <= 2 * min(blocks) + 4 * 60  # 특정 시간대에 몰리지 않음


def test_first_pick_is_the_first_new_candidate():
    assert pick_next_variation([A, B, C], None, [], MIDNIGHT, 240).id == B.id


def test_manual_swap_never_keeps_the_current_candidate():
    # 균형상 A 유지가 맞는 상황이어도 allow_stay=False면 다른 후보로 바꾼다
    exposures = [(B.id, MIDNIGHT - timedelta(hours=24), MIDNIGHT - timedelta(hours=12)), (A.id, MIDNIGHT - timedelta(hours=12), MIDNIGHT)]
    assert pick_next_variation([A, B], A, exposures, MIDNIGHT, 720).id == A.id
    assert pick_next_variation([A, B], A, exposures, MIDNIGHT, 720, allow_stay=False).id == B.id


def test_minutes_by_hour_splits_across_midnight_and_whole_days():
    buckets = minutes_by_hour(MIDNIGHT - timedelta(minutes=30), MIDNIGHT + timedelta(days=1, minutes=90))
    assert buckets[23] == 60 + 30  # 하루치 60분 + 자정 전 30분
    assert buckets[0] == 60 + 60 and buckets[1] == 60 + 30
    assert sum(buckets) == 24 * 60 + 120
