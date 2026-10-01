"""Sample-size and minimum-detectable-effect calculations (normal approximation)."""
import numpy as np
from scipy import stats


def sample_size_proportions(p_base: float, mde_rel: float, alpha=0.05, power=0.8) -> int:
    """Users needed PER ARM to detect a relative lift of mde_rel on a conversion rate."""
    p1, p2 = p_base, p_base * (1 + mde_rel)
    z_a, z_b = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    var = p1 * (1 - p1) + p2 * (1 - p2)
    return int(np.ceil((z_a + z_b) ** 2 * var / (p2 - p1) ** 2))


def mde_proportions(p_base: float, n_per_arm: int, alpha=0.05, power=0.8) -> float:
    """Smallest RELATIVE lift detectable with n_per_arm users per arm."""
    z_a, z_b = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    abs_mde = (z_a + z_b) * np.sqrt(2 * p_base * (1 - p_base) / n_per_arm)
    return float(abs_mde / p_base)


def sample_size_means(sd: float, mde_abs: float, alpha=0.05, power=0.8) -> int:
    """Users needed PER ARM to detect an absolute difference in means."""
    z_a, z_b = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    return int(np.ceil(2 * (z_a + z_b) ** 2 * sd**2 / mde_abs**2))


def days_needed(n_per_arm: int, users_per_day: int, treat_share=0.5) -> int:
    """Calendar days to reach n_per_arm in the smaller arm."""
    return int(np.ceil(n_per_arm / (users_per_day * min(treat_share, 1 - treat_share))))
