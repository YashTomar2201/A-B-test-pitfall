"""P6 - Segment p-hacking."""
import numpy as np
from scipy import stats


def _seg_z(rng, n_sims, n_seg, n_per_arm_seg, p, lift=0.0):
    ca = rng.binomial(n_per_arm_seg, p, size=(n_sims, n_seg))
    cb = rng.binomial(n_per_arm_seg, p * (1 + lift), size=(n_sims, n_seg))
    pa, pb = ca / n_per_arm_seg, cb / n_per_arm_seg
    pool = (ca + cb) / (2 * n_per_arm_seg)
    z = (pb - pa) / np.sqrt(np.maximum(pool * (1 - pool) * 2 / n_per_arm_seg, 1e-12))
    return z, (pb - pa) / np.maximum(pa, 1e-9)


def segment_hacking(n_segments=15, n_per_arm=28_000, p=0.05, n_sims=20_000, seed=0) -> dict:
    """True lift = 0 everywhere. Slice into n_segments after the fact and 'report the best'."""
    rng = np.random.default_rng(seed)
    n_seg = n_per_arm // n_segments
    z, rel = _seg_z(rng, n_sims, n_segments, n_seg, p)
    sig = np.abs(z) > 1.96
    any_sig = sig.any(1)
    best = np.argmax(np.abs(z), axis=1)
    best_rel = rel[np.arange(n_sims), best]
    z2, _ = _seg_z(rng, n_sims, 1, n_seg, p)          # follow-up on fresh data; true lift is still 0
    return {
        "n_segments": n_segments,
        "any_segment_significant": float(any_sig.mean()),
        "avg_reported_abs_lift_in_winner": float(np.abs(best_rel[any_sig]).mean()),
        "bonferroni_any_significant": float((np.abs(z) > stats.norm.ppf(1 - 0.025 / n_segments)).any(1).mean()),
        "followup_confirms": float((np.abs(z2[any_sig, 0]) > 1.96).mean()),
    }
