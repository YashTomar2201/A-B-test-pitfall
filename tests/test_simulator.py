import numpy as np
import pytest

from abtest.analyze.tests import two_prop_ztest
from abtest.simulate.engine import ExperimentConfig, simulate


def ztest_df(df):
    g = df.groupby("arm")["converted"].agg(["sum", "count"])
    return two_prop_ztest(g.loc["control", "sum"], g.loc["control", "count"],
                          g.loc["treatment", "sum"], g.loc["treatment", "count"])


def test_baseline_conversion_calibrated():
    df = simulate(ExperimentConfig(days=7, users_per_day=20_000, seed=0))
    assert abs(df["converted"].mean() - 0.05) < 0.002


def test_treatment_share():
    df = simulate(ExperimentConfig(days=7, users_per_day=10_000, seed=0))
    assert abs((df["arm"] == "treatment").mean() - 0.5) < 0.01


def test_reproducible_with_seed():
    a = simulate(ExperimentConfig(seed=7))
    b = simulate(ExperimentConfig(seed=7))
    assert a.equals(b)


def test_srm_injection_changes_split():
    df = simulate(ExperimentConfig(days=7, srm_drop_rate=0.05, seed=0))
    assert (df["arm"] == "treatment").mean() < 0.49


def test_ramp_changes_early_share():
    df = simulate(ExperimentConfig(days=6, ramp_days=2, ramp_treat_share=0.1, seed=0))
    early = df[df.day < 2]
    assert (early["arm"] == "treatment").mean() < 0.15


def test_daily_base_cr_changes_daily_rate():
    cfg = ExperimentConfig(days=4, users_per_day=30_000, daily_base_cr=(0.10, 0.10, 0.03, 0.03), seed=0)
    df = simulate(cfg)
    by_day = df.groupby("day")["converted"].mean()
    assert by_day[0] > 2 * by_day[3]


@pytest.mark.slow
def test_aa_false_positive_rate_is_5pct():
    rej = sum(ztest_df(simulate(ExperimentConfig(days=7, users_per_day=2_000, seed=s))).significant
              for s in range(1_000))
    assert 0.035 < rej / 1_000 < 0.065


@pytest.mark.slow
def test_known_effect_recovered_with_correct_coverage():
    base, lift = 0.05, 0.10
    true_abs = base * lift
    est, covered = [], 0
    for s in range(1_000):
        r = ztest_df(simulate(ExperimentConfig(days=7, users_per_day=4_000, lift=lift, seed=s)))
        est.append(r.effect)
        covered += r.ci_low <= true_abs <= r.ci_high
    assert abs(np.mean(est) - true_abs) < 0.1 * true_abs
    assert 0.93 < covered / 1_000 < 0.97
