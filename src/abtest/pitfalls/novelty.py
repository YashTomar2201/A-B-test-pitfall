"""P4 - Novelty effect."""
import numpy as np
import pandas as pd
from scipy import stats


def _daily(rng, n_sims, days, n_per_arm_day, p, true_lift, boost, halflife):
    d = np.arange(days)
    p_b = p * (1 + true_lift + boost * 0.5 ** (d / halflife))
    ca = rng.binomial(n_per_arm_day, p, size=(n_sims, days))
    cb = rng.binomial(n_per_arm_day, p_b, size=(n_sims, days))
    return ca, cb


def _window_ztest(ca, cb, n_day, lo, hi):
    a, b = ca[:, lo:hi].sum(1), cb[:, lo:hi].sum(1)
    n = n_day * (hi - lo)
    pa, pb = a / n, b / n
    pool = (a + b) / (2 * n)
    z = (pb - pa) / np.sqrt(np.maximum(pool * (1 - pool) * 2 / n, 1e-12))
    return pa, pb, z


def novelty_study(true_lift=0.0, boost=0.20, halflife=3.0, p=0.05, days=14, n_per_arm_day=2_000,
                  n_sims=5_000, seed=0) -> dict:
    rng = np.random.default_rng(seed)
    ca, cb = _daily(rng, n_sims, days, n_per_arm_day, p, true_lift, boost, halflife)
    out = {"true_long_run_lift": true_lift}
    for d in (3, 7, 14):
        pa, pb, z = _window_ztest(ca, cb, n_per_arm_day, 0, d)
        out[f"first_{d}d"] = {"avg_est_rel_lift": float(((pb - pa) / pa).mean()),
                              "reject_rate": float((np.abs(z) > 1.96).mean())}
    pa, pb, z = _window_ztest(ca, cb, n_per_arm_day, 7, 14)        # mature cohort: second week only
    out["second_week"] = {"avg_est_rel_lift": float(((pb - pa) / pa).mean()),
                          "reject_rate": float((np.abs(z) > 1.96).mean())}

    # Detection: weighted regression of the daily effect on the day; flag a significantly negative slope.
    pa_d, pb_d = ca / n_per_arm_day, cb / n_per_arm_day
    eff = pb_d - pa_d
    se = np.sqrt((pa_d * (1 - pa_d) + pb_d * (1 - pb_d)) / n_per_arm_day)
    x = np.arange(days, dtype=float)
    w = 1 / np.maximum(se, 1e-9) ** 2
    wsum = w.sum(1, keepdims=True)
    xw = (w * x).sum(1, keepdims=True) / wsum
    yw = (w * eff).sum(1, keepdims=True) / wsum
    sxx = (w * (x - xw) ** 2).sum(1)
    slope = (w * (x - xw) * (eff - yw)).sum(1) / sxx
    z_slope = slope / np.sqrt(1 / sxx)
    out["novelty_flagged"] = float((z_slope < stats.norm.ppf(0.05)).mean())     # one-sided 5%
    return out


def novelty_scenarios(seed=0, n_sims=5_000) -> pd.DataFrame:
    rows = []
    for name, lift, boost in [("no novelty, no effect", 0.0, 0.0), ("novelty only", 0.0, 0.20),
                              ("novelty + real lift", 0.05, 0.20), ("real lift only", 0.05, 0.0)]:
        r = novelty_study(true_lift=lift, boost=boost, n_sims=n_sims, seed=seed)
        rows.append({"scenario": name, "true_long_run_lift": lift,
                     "est_3d": r["first_3d"]["avg_est_rel_lift"], "reject_3d": r["first_3d"]["reject_rate"],
                     "est_14d": r["first_14d"]["avg_est_rel_lift"],
                     "est_week2": r["second_week"]["avg_est_rel_lift"],
                     "reject_week2": r["second_week"]["reject_rate"],
                     "novelty_flagged": r["novelty_flagged"]})
    return pd.DataFrame(rows)
