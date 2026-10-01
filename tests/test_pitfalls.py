import numpy as np

from abtest.analyze.cuped import cuped_adjust, variance_reduction
from abtest.analyze.tests import welch_ttest
from abtest.pitfalls import multiple_testing as mt
from abtest.pitfalls import peeking, segments, unit_of_analysis, winners_curse
from abtest.simulate.engine import ExperimentConfig, simulate


def test_peeking_inflates_false_positives():
    r = peeking.peeking_fpr(n_sims=4_000, days=14)
    assert r["fixed_horizon_fpr"] < 0.065
    assert r["daily_peeking_fpr"] > 0.15


def test_winners_curse_shrinks_with_power():
    low = winners_curse.winners_curse(true_rel_lift=0.10, n_per_arm=2_000, n_sims=20_000)
    high = winners_curse.winners_curse(true_rel_lift=0.10, n_per_arm=40_000, n_sims=20_000)
    assert low["exaggeration_ratio"] > 2.5 > 1.3 > high["exaggeration_ratio"] > 0.95


def test_holm_and_bh_control_error_when_uncorrected_does_not():
    r = mt.any_false_positive(n_metrics=20, rho=0.3, n_sims=10_000)
    assert r["uncorrected"] > 0.4
    assert r["holm"] < 0.065 and r["bh"] < 0.065


def test_holm_is_never_more_liberal_than_uncorrected():
    p = np.random.default_rng(0).uniform(size=(500, 12))
    assert not (mt.holm_reject(p) & ~(p < 0.05)).any()


def test_segment_hacking_matches_theory_and_bonferroni_fixes_it():
    r = segments.segment_hacking(n_segments=15, n_sims=10_000)
    assert abs(r["any_segment_significant"] - (1 - 0.95**15)) < 0.04
    assert r["bonferroni_any_significant"] < 0.065
    assert r["followup_confirms"] < 0.08


def test_unit_of_analysis_session_level_test_is_anticonservative():
    ua = unit_of_analysis.unit_of_analysis_fpr(user_sd_grid=(1.5,), n_sims=300)
    assert ua.naive_session_level_fpr.iloc[0] > 0.10
    assert ua.delta_method_fpr.iloc[0] < 0.09


def test_cuped_variance_reduction_follows_rho_squared():
    rng = np.random.default_rng(1)
    x = rng.standard_normal(100_000)
    for rho in (0.3, 0.6, 0.9):
        y = rho * x + np.sqrt(1 - rho**2) * rng.standard_normal(100_000)
        assert abs(variance_reduction(y, x) - rho**2) < 0.01


def test_cuped_keeps_aa_false_positive_rate():
    rej = 0
    for s in range(300):
        df = simulate(ExperimentConfig(days=7, users_per_day=1_500, seed=700 + s))
        t = (df.arm == "treatment").values
        yc = cuped_adjust(df.revenue.values, df.pre_spend.values)
        rej += welch_ttest(yc[~t], yc[t]).significant
    assert 0.02 < rej / 300 < 0.09
