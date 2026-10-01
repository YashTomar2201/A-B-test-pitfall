"""P3 - Sample ratio mismatch."""
import numpy as np
import pandas as pd

from abtest.analyze.tests import srm_test, two_prop_ztest
from abtest.simulate.engine import ExperimentConfig, simulate


def _one(cfg):
    df = simulate(cfg)
    g = df.groupby("arm")["converted"].agg(["sum", "count"])
    r = two_prop_ztest(g.loc["control", "sum"], g.loc["control", "count"],
                       g.loc["treatment", "sum"], g.loc["treatment", "count"])
    return r, srm_test(g.loc["control", "count"], g.loc["treatment", "count"])


def srm_damage(drop_rates=(0.0, 0.005, 0.01, 0.02, 0.03, 0.05), n_sims=300, days=7,
               users_per_day=6_000, seed=0) -> pd.DataFrame:
    """True lift = 0 throughout. Measure bias, false positive rate and SRM detection."""
    rows = []
    for d in drop_rates:
        eff, sig, flag = [], [], []
        for s in range(n_sims):
            cfg = ExperimentConfig(days=days, users_per_day=users_per_day, srm_drop_rate=d,
                                   seed=seed * 1_000_003 + s)
            r, p_srm = _one(cfg)
            eff.append(r.rel_lift)
            sig.append(r.significant)
            flag.append(p_srm < 0.001)
        rows.append({"drop_rate": d, "avg_fake_rel_lift": float(np.mean(eff)),
                     "false_positive_rate": float(np.mean(sig)), "srm_detected": float(np.mean(flag))})
    return pd.DataFrame(rows)


def srm_detection_by_size(users_per_day_grid=(500, 1_000, 2_000, 4_000, 8_000), drop_rate=0.02,
                          n_sims=300, days=7, seed=1) -> pd.DataFrame:
    rows = []
    for upd in users_per_day_grid:
        flags = [_one(ExperimentConfig(days=days, users_per_day=upd, srm_drop_rate=drop_rate,
                                       seed=seed * 1_000_003 + s))[1] < 0.001 for s in range(n_sims)]
        rows.append({"users_per_day": upd, "srm_detected": float(np.mean(flags))})
    return pd.DataFrame(rows)
