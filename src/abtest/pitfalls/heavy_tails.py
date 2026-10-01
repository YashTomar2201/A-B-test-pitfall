"""P7 - Heavy-tailed revenue metrics."""
import numpy as np
import pandas as pd

from abtest.analyze.cuped import cuped_adjust
from abtest.analyze.tests import bootstrap_diff_ci, welch_ttest
from abtest.simulate.engine import ExperimentConfig, simulate


def winsorize_pooled(rev, q=0.99):
    """Cap at the POOLED q-quantile (per-arm caps would bias the comparison).
    Note: this estimates the effect on capped revenue, not on true revenue."""
    return np.minimum(rev, np.quantile(rev, q))


def heavy_tail_study(whale_rates=(0.0, 0.001, 0.005, 0.01), lifts=(0.0, 0.10), n_sims=400,
                     days=14, users_per_day=2_000, use_bootstrap=False, n_boot_sims=100,
                     seed=0) -> pd.DataFrame:
    rows = []
    for w in whale_rates:
        for lift in lifts:
            rej = {"welch": 0, "winsorized_p99": 0, "cuped": 0, "bootstrap": 0}
            for s in range(n_sims):
                df = simulate(ExperimentConfig(days=days, users_per_day=users_per_day, lift=lift,
                                               whale_rate=w, seed=seed * 1_000_003 + s))
                t = (df["arm"] == "treatment").values
                y = df["revenue"].values
                rej["welch"] += welch_ttest(y[~t], y[t]).significant
                yw = winsorize_pooled(y)
                rej["winsorized_p99"] += welch_ttest(yw[~t], yw[t]).significant
                yc = cuped_adjust(y, df["pre_spend"].values)
                rej["cuped"] += welch_ttest(yc[~t], yc[t]).significant
                if use_bootstrap and s < n_boot_sims:
                    lo, hi = bootstrap_diff_ci(y[~t], y[t], n_boot=300, seed=s)
                    rej["bootstrap"] += not (lo <= 0 <= hi)
            for k, v in rej.items():
                if k == "bootstrap" and not use_bootstrap:
                    continue
                denom = min(n_sims, n_boot_sims) if k == "bootstrap" else n_sims
                rows.append({"whale_rate": w, "true_conv_lift": lift, "method": k, "reject_rate": v / denom})
    return pd.DataFrame(rows)
