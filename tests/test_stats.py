import numpy as np
from scipy import stats
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize, proportions_ztest

from abtest.analyze.power import days_needed, mde_proportions, sample_size_proportions
from abtest.analyze.tests import (bootstrap_diff_ci, delta_method_ratio, srm_test,
                                  two_prop_ztest, welch_ttest)


def test_ztest_matches_statsmodels():
    r = two_prop_ztest(500, 10_000, 560, 10_000)
    _, p_sm = proportions_ztest([560, 500], [10_000, 10_000])
    assert abs(r.p_value - p_sm) < 1e-10


def test_ztest_ci_contains_point_estimate():
    r = two_prop_ztest(500, 10_000, 560, 10_000)
    assert r.ci_low < r.effect < r.ci_high


def test_welch_matches_scipy():
    rng = np.random.default_rng(0)
    a, b = rng.normal(10, 3, 500), rng.normal(10.5, 5, 800)
    r = welch_ttest(a, b)
    assert abs(r.p_value - stats.ttest_ind(b, a, equal_var=False).pvalue) < 1e-10


def test_bootstrap_ci_brackets_true_difference():
    rng = np.random.default_rng(1)
    a, b = rng.normal(10, 2, 2000), rng.normal(11, 2, 2000)
    lo, hi = bootstrap_diff_ci(a, b, n_boot=500, seed=2)
    assert lo < 1.0 < hi


def test_delta_method_matches_user_level_mean_when_denominator_constant():
    rng = np.random.default_rng(3)
    a, b = rng.normal(5, 2, 3000), rng.normal(5.2, 2, 3000)
    ones = np.ones(3000)
    r = delta_method_ratio(a, ones, b, ones)
    w = welch_ttest(a, b)
    assert abs(r.se - w.se) / w.se < 0.01


def test_srm_flags_obvious_imbalance():
    assert srm_test(50_000, 50_000) > 0.5
    assert srm_test(50_000, 48_500) < 0.001


def test_srm_respects_expected_share():
    assert srm_test(15_000, 85_000, expected_share_b=0.85) > 0.001


def test_sample_size_close_to_statsmodels():
    ours = sample_size_proportions(0.05, 0.10)
    h = proportion_effectsize(0.055, 0.05)
    theirs = NormalIndPower().solve_power(h, alpha=0.05, power=0.8, ratio=1)
    assert abs(ours - theirs) / theirs < 0.03


def test_mde_and_sample_size_are_inverse():
    n = sample_size_proportions(0.05, 0.10)
    assert abs(mde_proportions(0.05, n) - 0.10) < 0.005


def test_days_needed():
    assert days_needed(20_000, 4_000) == 10
