"""P5 - Multiple metrics and variants."""
import numpy as np
import pandas as pd
from scipy import stats


def holm_reject(p: np.ndarray, alpha=0.05) -> np.ndarray:
    """Holm-Bonferroni (controls family-wise error rate). p has shape (sims, m)."""
    m = p.shape[1]
    order = np.argsort(p, axis=1)
    sorted_p = np.take_along_axis(p, order, 1)
    ok = sorted_p <= alpha / (m - np.arange(m))
    passed = np.cumprod(ok, axis=1).astype(bool)          # reject up to the first failure
    rej = np.zeros_like(passed)
    np.put_along_axis(rej, order, passed, 1)
    return rej


def bh_reject(p: np.ndarray, alpha=0.05) -> np.ndarray:
    """Benjamini-Hochberg (controls false discovery rate)."""
    m = p.shape[1]
    order = np.argsort(p, axis=1)
    sorted_p = np.take_along_axis(p, order, 1)
    ok = sorted_p <= alpha * (np.arange(m) + 1) / m
    k = np.where(ok.any(1), m - np.argmax(ok[:, ::-1], axis=1), 0)       # largest passing rank
    passed = np.arange(m)[None, :] < k[:, None]
    rej = np.zeros_like(passed)
    np.put_along_axis(rej, order, passed, 1)
    return rej


def null_pvalues(n_metrics, rho, n_sims, rng):
    cov = np.full((n_metrics, n_metrics), rho) + (1 - rho) * np.eye(n_metrics)
    z = rng.multivariate_normal(np.zeros(n_metrics), cov, size=n_sims)
    return 2 * stats.norm.sf(np.abs(z))


def any_false_positive(n_metrics=20, rho=0.3, n_sims=20_000, seed=0) -> dict:
    rng = np.random.default_rng(seed)
    p = null_pvalues(n_metrics, rho, n_sims, rng)
    return {"uncorrected": float((p < 0.05).any(1).mean()),
            "holm": float(holm_reject(p).any(1).mean()),
            "bh": float(bh_reject(p).any(1).mean())}


def fpr_vs_metrics(metric_grid=(1, 2, 3, 5, 10, 20, 50), rho=0.3, n_sims=20_000, seed=0) -> pd.DataFrame:
    return pd.DataFrame([{"n_metrics": m, **any_false_positive(m, rho, n_sims, seed)} for m in metric_grid])


def multiple_variants(n_variants=(2, 3, 5, 8), n_sims=20_000, seed=0) -> pd.DataFrame:
    """A/B/C/...: every variant is compared to the same control, so the tests are correlated (~0.5)."""
    rng = np.random.default_rng(seed)
    rows = []
    for v in n_variants:
        k = v - 1
        p = null_pvalues(k, 0.5 if k > 1 else 0.0, n_sims, rng)
        rows.append({"n_variants": v, "uncorrected": float((p < 0.05).any(1).mean()),
                     "holm": float(holm_reject(p).any(1).mean())})
    return pd.DataFrame(rows)
