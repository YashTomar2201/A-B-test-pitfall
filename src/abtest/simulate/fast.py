"""Aggregate (count-based) simulator: binomial counts are sufficient statistics for a
two-proportion z-test, so results match the user-level engine but run ~100x faster."""
import numpy as np


def daily_counts(rng, n_sims: int, days: int, n_per_arm_day: int, p_a, p_b):
    """Cumulative conversions per arm and cumulative users per arm, shape (n_sims, days).
    p_b may be an array of length `days` (e.g. a decaying novelty effect)."""
    p_a = np.broadcast_to(p_a, (days,))
    p_b = np.broadcast_to(p_b, (days,))
    conv_a = rng.binomial(n_per_arm_day, p_a, size=(n_sims, days)).cumsum(axis=1)
    conv_b = rng.binomial(n_per_arm_day, p_b, size=(n_sims, days)).cumsum(axis=1)
    n = n_per_arm_day * np.arange(1, days + 1)
    return conv_a, conv_b, n


def ztest_vectorized(conv_a, conv_b, n):
    """Pooled two-proportion z statistic, elementwise. n is users per arm."""
    p_a, p_b = conv_a / n, conv_b / n
    pool = (conv_a + conv_b) / (2 * n)
    se = np.sqrt(np.maximum(pool * (1 - pool) * 2 / n, 1e-12))
    return (p_b - p_a) / se
