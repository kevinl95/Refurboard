import math

from refurboard_py.detection import AdaptiveThreshold, Smoother


def test_adaptive_threshold_hysteresis_behavior():
    threshold = AdaptiveThreshold(sensitivity=0.5, hysteresis=0.25)

    # First signal seeds the baseline and should not immediately click
    assert threshold.evaluate(10.0) is False

    # Strong signal comfortably above the dynamic high threshold should activate
    assert threshold.evaluate(20.0) is True

    # Drop slightly but stay above the low threshold -> remains active
    still_active = threshold.evaluate(15.0)
    assert still_active is True, "Hysteresis should prevent flicker when signal is high"

    # Large drop below the low threshold should release
    released = threshold.evaluate(5.0)
    assert released is False


def test_smoother_exponential_decay():
    # Disable reacquisition filter (reacquire_frames=0) to test pure smoothing
    smoother = Smoother(factor=0.25, reacquire_frames=0)

    # First update should echo the sample
    assert smoother.update((0.0, 0.0)) == (0.0, 0.0)

    # Subsequent updates move a quarter of the distance toward the new point
    x1, y1 = smoother.update((1.0, 1.0))
    assert math.isclose(x1, 0.25, rel_tol=1e-5)
    assert math.isclose(y1, 0.25, rel_tol=1e-5)

    x2, y2 = smoother.update((1.0, 1.0))
    # After the second blend the cursor should be 0.4375 (0.25 + 0.25 * 0.75)
    assert math.isclose(x2, 0.4375, rel_tol=1e-5)
    assert math.isclose(y2, 0.4375, rel_tol=1e-5)

    # Provide a new point and ensure the accumulator moves toward it smoothly
    x3, y3 = smoother.update((0.0, 1.0))
    expected = (
        0.4375 * (1 - 0.25) + 0.0 * 0.25,
        0.4375 * (1 - 0.25) + 1.0 * 0.25,
    )
    assert math.isclose(x3, expected[0], rel_tol=1e-5)
    assert math.isclose(y3, expected[1], rel_tol=1e-5)
