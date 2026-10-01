"""P2 - Underpowered tests and the winner's curse (Type M and Type S errors)."""
import numpy as np
import pandas as pd

from abtest.analyze.power import sample_size_proportions
from abtest.simulate.fast import ztest_vectorized


def winners_curse(true_rel_lift=0.02, p=0.05, n_per_arm=10_000, n_sims=20_000, seed=0) -> dict:
    rng = np.random.default_rng(seed)
    ca = rng.binomial(n_per_arm, p, n_sims)
    cb = rng.binomial(n_per_arm, p * (1 + true_rel_lift), n_sims)
    z = ztest_vectorized(ca, cb, n_per_arm)
    est = (cb - ca) / np.maximum(ca, 1)                # estimated relative lift
    sig = np.abs(z) > 1.96
    if sig.sum() == 0:
        return {"power": 0.0, "exaggeration_ratio": np.nan, "wrong_sign_share": np.nan}
    return {
        "power": float(sig.mean()),
        "exaggeration_ratio": float(np.abs(est[sig]).mean() / true_rel_lift),   # Type M
        "wrong_sign_share": float((est[sig] < 0).mean()),                       # Type S
    }


def exaggeration_vs_power(target_powers=(0.10, 0.20, 0.30, 0.50, 0.70, 0.80, 0.90), true_rel_lift=0.10,
                          p=0.05, **kw) -> pd.DataFrame:
    """Size each test for a target power (via the power formula), then measure exaggeration."""
    rows = []
    for q in target_powers:
        n = sample_size_proportions(p, true_rel_lift, power=q)
        rows.append({"target_power": q, "n_per_arm": n,
                     **winners_curse(true_rel_lift=true_rel_lift, p=p, n_per_arm=n, **kw)})
    return pd.DataFrame(rows)
