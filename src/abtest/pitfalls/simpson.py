"""P9 - Simpson's paradox during ramp-up."""
import numpy as np

from abtest.analyze.tests import two_prop_ztest
from abtest.simulate.engine import ExperimentConfig, simulate


def stratified_effect(df) -> float:
    """Weighted average of the per-day treatment-minus-control difference."""
    g = df.groupby(["day", "arm"])["converted"].agg(["mean", "count"]).unstack("arm")
    w = g[("count", "control")] + g[("count", "treatment")]
    diff = g[("mean", "treatment")] - g[("mean", "control")]
    return float(np.average(diff, weights=w))


def simpson_study(n_sims=400, days=14, users_per_day=6_000, ramp_days=3, ramp_share=0.10,
                  sale_cr=0.08, normal_cr=0.04, seed=0) -> dict:
    """No true effect. The test ramps at 10% treatment during a high-conversion sale, then 50%."""
    daily = tuple([sale_cr] * ramp_days + [normal_cr] * (days - ramp_days))
    pooled_est, strat_est, pooled_sig = [], [], 0
    for s in range(n_sims):
        df = simulate(ExperimentConfig(days=days, users_per_day=users_per_day, daily_base_cr=daily,
                                       ramp_days=ramp_days, ramp_treat_share=ramp_share,
                                       lift=0.0, seed=seed * 1_000_003 + s))
        g = df.groupby("arm")["converted"].agg(["sum", "count"])
        r = two_prop_ztest(g.loc["control", "sum"], g.loc["control", "count"],
                           g.loc["treatment", "sum"], g.loc["treatment", "count"])
        pooled_est.append(r.effect)
        pooled_sig += r.significant
        strat_est.append(stratified_effect(df))
    return {"true_effect": 0.0, "pooled_avg_effect": float(np.mean(pooled_est)),
            "stratified_avg_effect": float(np.mean(strat_est)),
            "pooled_false_positive_rate": pooled_sig / n_sims}
