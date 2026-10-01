"""Sequential testing: group-sequential O'Brien-Fleming boundaries and mSPRT."""
import numpy as np


def calibrate_obf(n_looks: int, alpha=0.05, n_sims=200_000, seed=0) -> float:
    """Reject at look k if |z_k| > c * sqrt(K / k). Find c so overall FPR = alpha."""
    rng = np.random.default_rng(seed)
    k = np.arange(1, n_looks + 1)
    z = rng.standard_normal((n_sims, n_looks)).cumsum(axis=1) / np.sqrt(k)
    stat = np.max(np.abs(z) / np.sqrt(n_looks / k), axis=1)
    return float(np.quantile(stat, 1 - alpha))


def obf_boundaries(n_looks: int, c: float) -> np.ndarray:
    k = np.arange(1, n_looks + 1)
    return c * np.sqrt(n_looks / k)


def msprt_pvalues(conv_a, conv_b, n_a, n_b, tau2: float):
    """Normal-mixture SPRT on the difference in proportions (Johari et al.).
    Inputs are cumulative arrays over looks (last axis = time). Returns always-valid
    p-values: the running minimum of 1/likelihood-ratio, so any look can stop the test."""
    pa, pb = conv_a / n_a, conv_b / n_b
    theta = pb - pa
    V = np.maximum(pa * (1 - pa) / n_a + pb * (1 - pb) / n_b, 1e-12)
    lam = np.sqrt(V / (V + tau2)) * np.exp(tau2 * theta**2 / (2 * V * (V + tau2)))
    return np.minimum.accumulate(np.minimum(1.0, 1.0 / lam), axis=-1)
