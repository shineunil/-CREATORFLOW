import os

# 승자 확정 전 최소로 보장할 A/B/C 순환 사이클 수 (시간대 편향 완화)
MIN_CYCLES = int(os.getenv("MIN_TEST_CYCLES", "2"))

# 승자 확정에 필요한 최소 누적 조회수 증가량 (표본이 너무 적으면 승자를 확정하지 않음)
MIN_SAMPLE_VIEWS = int(os.getenv("MIN_WINNER_SAMPLE_VIEWS", "50"))

# 사이클/표본이 부족할 때 자동으로 테스트 기간을 연장하는 최대 횟수 (무한 연장 방지)
MAX_AUTO_EXTENSIONS = int(os.getenv("MAX_AUTO_TEST_EXTENSIONS", "2"))

# 스왑 직후 워밍업 구간(분) - 직전 썸네일의 잔상 노출 효과를 점수에서 배제하기 위해
# 이 기간이 지난 뒤에 조회수 기준선을 다시 캡처한다
SWAP_WARMUP_MINUTES = int(os.getenv("SWAP_WARMUP_MINUTES", "15"))

# BASIC 요금제가 선택할 수 있는 최소 교체 주기(분). 이보다 짧은 주기는 PRO 전용.
BASIC_MIN_SWAP_INTERVAL_MINUTES = int(os.getenv("BASIC_MIN_SWAP_INTERVAL_MINUTES", "240"))  # 4시간

# 채널당 동시 진행 가능한 테스트 개수의 절대 상한 (요금제 무관, PRO/AGENCY도 적용).
# YouTube Data API 쿼터는 프로젝트 전체 공유 자원이라, 한 채널이 무제한으로 테스트를
# 돌리면 다른 유저까지 영향을 받을 수 있어 시스템 보호 차원의 안전장치로 둔다.
# (BASIC은 이 값과 무관하게 별도로 더 낮은 1개 제한이 적용됨)
MAX_CONCURRENT_TESTS_PER_CHANNEL = int(os.getenv("MAX_CONCURRENT_TESTS_PER_CHANNEL", "20"))

# 한 계정(User)에 연동할 수 있는 YouTube 채널 개수 상한 (요금제별). 멀티채널 관리가
# 에이전시/PRO 요금제의 핵심 차별화 지점이므로 BASIC은 1개로 제한한다.
MAX_CHANNELS_PER_PLAN = {
    "BASIC": int(os.getenv("MAX_CHANNELS_BASIC", "1")),
    "PRO": int(os.getenv("MAX_CHANNELS_PRO", "3")),
    "AGENCY": int(os.getenv("MAX_CHANNELS_AGENCY", "20")),
}


def max_channels_for_plan(plan_value: str) -> int:
    return MAX_CHANNELS_PER_PLAN.get(plan_value, MAX_CHANNELS_PER_PLAN["BASIC"])


def has_enough_cycles(measured_windows: list[int]) -> bool:
    """
    measured_windows: 후보마다 지금까지 측정된(걸려 있다가 기록된) 구간 수.
    후보를 시간대 균형에 맞춰 고르기 때문에 순서가 고정돼 있지 않다. 전체 교체 횟수 대신
    모든 후보가 각각 MIN_CYCLES번 이상 측정됐는지로 본다 - 한 후보만 덜 걸린 채 승자가 정해지지 않게.
    """
    if not measured_windows:
        return False
    return min(measured_windows) >= MIN_CYCLES


def has_enough_sample(total_views_gained: int) -> bool:
    return total_views_gained >= MIN_SAMPLE_VIEWS
