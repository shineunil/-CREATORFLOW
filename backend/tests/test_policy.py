from test_policy import has_enough_cycles, has_enough_sample, MIN_CYCLES, MIN_SAMPLE_VIEWS


def test_has_enough_cycles_when_every_candidate_reached_the_threshold():
    assert has_enough_cycles([MIN_CYCLES, MIN_CYCLES, MIN_CYCLES + 3]) is True


def test_one_under_measured_candidate_blocks_the_winner():
    # 전체 측정 횟수는 충분해도, 한 후보라도 덜 걸렸으면 아직 승자를 정하지 않는다
    assert has_enough_cycles([MIN_CYCLES + 5, MIN_CYCLES + 5, MIN_CYCLES - 1]) is False


def test_has_enough_cycles_zero_variations_is_never_enough():
    assert has_enough_cycles([]) is False


def test_has_enough_sample_at_threshold():
    assert has_enough_sample(MIN_SAMPLE_VIEWS) is True


def test_has_enough_sample_below_threshold():
    assert has_enough_sample(MIN_SAMPLE_VIEWS - 1) is False
