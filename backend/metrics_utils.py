def compute_variation_vph(variation) -> float:
    """
    변인(Variation)의 시간당 조회수(VPH) = 누적 조회수 증가 / 누적 노출 시간.
    노출 시간을 전혀 측정하지 못한 경우(레거시 데이터, 또는 스왑과 측정이 같은 순간에 겹쳐
    hours_exposed가 0으로 반올림된 경우) raw 조회수 합계로 폴백하면, 그 값이 "시간당 조회수"
    스케일의 다른 변인들과 직접 비교되면서 승자 판정을 왜곡시킬 수 있다(예: 노출 30분 만에
    5회 조회된 변인의 진짜 VPH는 10인데, 노출 시간이 0으로 기록된 변인이 조회수 5회만으로
    VPH=5.0을 반환하며 실제 성과와 무관하게 비교에 낄 수 있음 — 극단적으로는 raw합계가 커서
    실제 VPH가 훨씬 높은 변인을 이겨버릴 수도 있다). 신뢰할 수 있는 비율을 계산할 수 없는
    경우엔 "아직 유의미한 성과 없음"을 뜻하는 0.0을 반환해, 실측된 변인들에게 밀리도록 한다.
    """
    logs = variation.metric_logs
    total_views = sum(l.views_gained for l in logs)
    total_hours = sum((l.hours_exposed or 0) for l in logs)
    if total_hours > 0:
        return total_views / total_hours
    return 0.0
