from test_policy import has_enough_cycles, has_enough_sample, MIN_CYCLES, MIN_SAMPLE_VIEWS


def test_has_enough_cycles_true_at_exact_threshold():
    assert has_enough_cycles(swap_count=MIN_CYCLES * 3, variation_count=3) is True


def test_has_enough_cycles_false_just_below_threshold():
    assert has_enough_cycles(swap_count=MIN_CYCLES * 3 - 1, variation_count=3) is False


def test_has_enough_cycles_zero_variations_is_never_enough():
    assert has_enough_cycles(swap_count=1000, variation_count=0) is False


def test_has_enough_sample_at_threshold():
    assert has_enough_sample(MIN_SAMPLE_VIEWS) is True


def test_has_enough_sample_below_threshold():
    assert has_enough_sample(MIN_SAMPLE_VIEWS - 1) is False
