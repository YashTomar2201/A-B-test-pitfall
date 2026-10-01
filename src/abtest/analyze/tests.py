"""Core hypothesis tests. Every function returns a TestResult for a uniform interface."""
from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass
class TestResult:
    effect: float          # treatment - control (absolute)
    se: float
    p_value: float
    ci_low: float
    ci_high: float
    rel_lift: float        # effect / control mean

    __test__ = False       # stop pytest collecting this as a test class

    @property
    def significant(self) -> bool:
        return self.p_value < 0.05


def two_prop_ztest(conv_a, n_a, conv_b, n_b, alpha: float = 0.05) -> TestResult:
    """Pooled SE for the test statistic (matches statsmodels); unpooled SE for the CI."""
    p_a, p_b = conv_a / n_a, conv_b / n_b
    p_pool = (conv_a + conv_b) / (n_a + n_b)
    se_pool = np.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    diff = p_b - p_a
    z = diff / se_pool if se_pool > 0 else 0.0
    p = 2 * stats.norm.sf(abs(z))
    se_ci = np.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    h = stats.norm.ppf(1 - alpha / 2) * se_ci
    return TestResult(diff, se_ci, p, diff - h, diff + h, diff / p_a if p_a else np.nan)


def welch_ttest(a, b, alpha: float = 0.05) -> TestResult:
    a, b = np.asarray(a, float), np.asarray(b, float)
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    se = np.sqrt(va + vb)
    dof = (va + vb) ** 2 / (va**2 / (len(a) - 1) + vb**2 / (len(b) - 1))
    diff = b.mean() - a.mean()
    p = 2 * stats.t.sf(abs(diff / se), dof)
    h = stats.t.ppf(1 - alpha / 2, dof) * se
    return TestResult(diff, se, p, diff - h, diff + h, diff / a.mean() if a.mean() else np.nan)


def bootstrap_diff_ci(a, b, n_boot: int = 2000, alpha: float = 0.05, seed=None):
    """Percentile bootstrap CI for the difference in means. Use for heavy-tailed metrics."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a, float), np.asarray(b, float)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        diffs[i] = rng.choice(b, len(b)).mean() - rng.choice(a, len(a)).mean()
    return tuple(np.quantile(diffs, [alpha / 2, 1 - alpha / 2]))


def _ratio_and_var(num, den):
    """Delta-method variance of mean(num)/mean(den), one row per randomization unit."""
    n = len(num)
    mx, my = den.mean(), num.mean()
    vx, vy = den.var(ddof=1), num.var(ddof=1)
    cxy = np.cov(num, den, ddof=1)[0, 1]
    r = my / mx
    var_r = (vy / mx**2 - 2 * my * cxy / mx**3 + my**2 * vx / mx**4) / n
    return r, var_r


def delta_method_ratio(num_a, den_a, num_b, den_b, alpha: float = 0.05) -> TestResult:
    """Ratio metrics (AOV = revenue/orders, CTR = clicks/sessions) randomized by user."""
    r_a, v_a = _ratio_and_var(np.asarray(num_a, float), np.asarray(den_a, float))
    r_b, v_b = _ratio_and_var(np.asarray(num_b, float), np.asarray(den_b, float))
    diff, se = r_b - r_a, np.sqrt(v_a + v_b)
    p = 2 * stats.norm.sf(abs(diff / se))
    h = stats.norm.ppf(1 - alpha / 2) * se
    return TestResult(diff, se, p, diff - h, diff + h, diff / r_a if r_a else np.nan)


def srm_test(n_a: int, n_b: int, expected_share_b: float = 0.5) -> float:
    """Chi-square goodness-of-fit p-value for the observed split. Flag if p < 0.001."""
    total = n_a + n_b
    expected = [total * (1 - expected_share_b), total * expected_share_b]
    return float(stats.chisquare([n_a, n_b], f_exp=expected).pvalue)
