from types import SimpleNamespace

from metrics_utils import compute_variation_vph


def make_variation(logs):
    """logs: list of (views_gained, hours_exposed) tuples"""
    return SimpleNamespace(
        metric_logs=[SimpleNamespace(views_gained=v, hours_exposed=h) for v, h in logs]
    )


def test_vph_basic_ratio():
    var = make_variation([(100, 2.0), (50, 1.0)])
    assert compute_variation_vph(var) == 50.0  # (100+50) views / (2+1) hours


def test_vph_no_logs_is_zero():
    var = make_variation([])
    assert compute_variation_vph(var) == 0.0


def test_vph_returns_zero_when_no_hours_exposed_recorded():
    # 노출 시간을 측정하지 못한 경우(레거시 데이터, 또는 스왑과 측정이 겹쳐 hours_exposed가 0으로
    # 반올림된 경우) raw 조회수 합계를 VPH처럼 반환하면 다른 변인의 진짜 VPH와 스케일이 달라
    # 승자 판정이 왜곡된다. 신뢰 가능한 비율이 없으므로 0.0(유의미한 성과 없음)을 반환해야 한다.
    var = make_variation([(80, 0), (20, 0)])
    assert compute_variation_vph(var) == 0.0


def test_vph_none_hours_exposed_treated_as_zero():
    var = SimpleNamespace(metric_logs=[SimpleNamespace(views_gained=10, hours_exposed=None)])
    assert compute_variation_vph(var) == 0.0
