"""P1 - Peeking / optional stopping."""
import numpy as np
import pandas as pd
from scipy import stats

from abtest.analyze.sequential import calibrate_obf, msprt_pvalues, obf_boundaries
from abtest.simulate.fast import daily_counts, ztest_vectorized

Z_CRIT = stats.norm.ppf(0.975)


def _looks(rng, n_sims, n_looks, n_total_per_arm, p_a, p_b):
    """Cumulative counts at n_looks equally spaced looks over a fixed total sample."""
    chunk = max(n_total_per_arm // n_looks, 1)
    return daily_counts(rng, n_sims, n_looks, chunk, p_a, p_b)


def peeking_fpr(n_sims=10_000, days=14, users_per_day=4_000, p=0.05, alpha=0.05, seed=0):
    """A/A test: false positive rate with one look vs stopping at the first p < alpha."""
    rng = np.random.default_rng(seed)
    ca, cb, n = daily_counts(rng, n_sims, days, users_per_day // 2, p, p)
    sig = np.abs(ztest_vectorized(ca, cb, n)) > stats.norm.ppf(1 - alpha / 2)
    return {"fixed_horizon_fpr": float(sig[:, -1].mean()),
            "daily_peeking_fpr": float(sig.any(axis=1).mean())}


def fpr_by_looks(looks=(1, 2, 3, 5, 7, 14, 28, 56), n_total_per_arm=28_000, p=0.05,
                 n_sims=10_000, seed=0) -> pd.DataFrame:
    """False positive rate as the number of looks grows (same total sample)."""
    rng = np.random.default_rng(seed)
    rows = []
    for k in looks:
        ca, cb, n = _looks(rng, n_sims, k, n_total_per_arm, p, p)
        sig = np.abs(ztest_vectorized(ca, cb, n)) > Z_CRIT
        rows.append({"looks": k, "fpr": float(sig.any(axis=1).mean())})
    return pd.DataFrame(rows)


def compare_methods(n_looks=14, n_total_per_arm=28_000, p=0.05, rel_lift=0.0, tau=0.0025,
                    n_sims=10_000, seed=1, c_obf=None) -> dict:
    """Rejection rate and average stopping look for each stopping rule at a given true lift."""
    rng = np.random.default_rng(seed)
    c = c_obf if c_obf is not None else calibrate_obf(n_looks, seed=seed)
    ca, cb, n = _looks(rng, n_sims, n_looks, n_total_per_arm, p, p * (1 + rel_lift))
    z = np.abs(ztest_vectorized(ca, cb, n))
    out = {}

    def summarise(rej_matrix):
        rej = rej_matrix.any(axis=1)
        first = np.where(rej, rej_matrix.argmax(axis=1) + 1, n_looks)
        return {"reject_rate": float(rej.mean()), "avg_looks_used": float(first.mean())}

    out["fixed_horizon"] = {"reject_rate": float((z[:, -1] > Z_CRIT).mean()), "avg_looks_used": float(n_looks)}
    out["naive_peeking"] = summarise(z > Z_CRIT)
    out["obrien_fleming"] = summarise(z > obf_boundaries(n_looks, c))
    pv = msprt_pvalues(ca, cb, n, n, tau2=tau**2)
    out["msprt"] = summarise(pv < 0.05)
    out["obf_constant"] = c
    return out


def msprt_tau_sensitivity(taus=(0.0005, 0.001, 0.0025, 0.005, 0.01), n_looks=14,
                          n_total_per_arm=28_000, p=0.05, rel_lift=0.10,
                          n_sims=5_000, seed=2) -> pd.DataFrame:
    rng_a = np.random.default_rng(seed)
    ca, cb, n = _looks(rng_a, n_sims, n_looks, n_total_per_arm, p, p)
    rng_b = np.random.default_rng(seed + 1)
    ca2, cb2, _ = _looks(rng_b, n_sims, n_looks, n_total_per_arm, p, p * (1 + rel_lift))
    rows = []
    for tau in taus:
        fpr = (msprt_pvalues(ca, cb, n, n, tau**2) < 0.05).any(axis=1).mean()
        pw = (msprt_pvalues(ca2, cb2, n, n, tau**2) < 0.05).any(axis=1).mean()
        rows.append({"tau": tau, "fpr": float(fpr), "power": float(pw)})
    return pd.DataFrame(rows)


def msprt_sample_cost(tau=0.005, multipliers=(1.0, 1.25, 1.5, 2.0, 2.5, 3.0), n_looks=14,
                      base_n_per_arm=28_000, p=0.05, rel_lift=0.10, n_sims=5_000, seed=3) -> pd.DataFrame:
    """Power of mSPRT as the planned sample grows: what 'look any time' costs in extra users."""
    rows = []
    for m in multipliers:
        rng = np.random.default_rng(seed)
        ca, cb, n = _looks(rng, n_sims, n_looks, int(base_n_per_arm * m), p, p * (1 + rel_lift))
        pw = (msprt_pvalues(ca, cb, n, n, tau**2) < 0.05).any(axis=1).mean()
        rows.append({"sample_multiplier": m, "msprt_power": float(pw)})
    return pd.DataFrame(rows)
