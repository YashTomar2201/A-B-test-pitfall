import numpy as np
import pytest
from scipy import stats

from abtest.analyze.sequential import calibrate_obf, msprt_pvalues, obf_boundaries
from abtest.simulate.fast import daily_counts, ztest_vectorized


def test_obf_constant_matches_published_value():
    # Published O'Brien-Fleming constant for 5 equally spaced looks at alpha = 0.05 is about 2.04.
    assert abs(calibrate_obf(5, n_sims=200_000, seed=1) - 2.04) < 0.04


def test_obf_boundaries_decrease_towards_the_end():
    b = obf_boundaries(5, 2.04)
    assert np.all(np.diff(b) < 0)
    assert abs(b[-1] - 2.04) < 1e-9


def test_naive_peeking_inflates_but_obf_and_msprt_hold_alpha():
    rng = np.random.default_rng(0)
    ca, cb, n = daily_counts(rng, 6_000, 10, 2_000, 0.05, 0.05)
    z = np.abs(ztest_vectorized(ca, cb, n))
    naive = (z > 1.96).any(1).mean()
    c = calibrate_obf(10, n_sims=100_000, seed=2)
    obf = (z > obf_boundaries(10, c)).any(1).mean()
    msprt = (msprt_pvalues(ca, cb, n, n, tau2=0.005**2) < 0.05).any(1).mean()
    assert naive > 0.15
    assert 0.035 < obf < 0.065
    assert msprt < 0.065


def test_msprt_pvalues_are_non_increasing_and_bounded():
    rng = np.random.default_rng(3)
    ca, cb, n = daily_counts(rng, 50, 14, 2_000, 0.05, 0.055)
    p = msprt_pvalues(ca, cb, n, n, tau2=0.005**2)
    assert np.all(p <= 1.0) and np.all(np.diff(p, axis=1) <= 1e-12)
