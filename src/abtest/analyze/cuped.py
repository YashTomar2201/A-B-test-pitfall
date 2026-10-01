"""CUPED variance reduction (Deng et al. 2013) and multi-covariate regression adjustment."""
import numpy as np
import statsmodels.api as sm

from abtest.analyze.tests import welch_ttest


def cuped_theta(y, x) -> float:
    y, x = np.asarray(y, float), np.asarray(x, float)
    return float(np.cov(y, x, ddof=1)[0, 1] / np.var(x, ddof=1))


def cuped_adjust(y, x):
    """Y_cuped = Y - theta * (X - mean(X)). theta is computed on BOTH arms pooled."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    return y - cuped_theta(y, x) * (x - x.mean())


def cuped_test(df, metric="revenue", covariate="pre_spend", arm_col="arm", treat_label="treatment"):
    adj = cuped_adjust(df[metric].values, df[covariate].values)
    t = (df[arm_col] == treat_label).values
    return welch_ttest(adj[~t], adj[t])


def variance_reduction(y, x) -> float:
    """Share of variance removed: 1 - Var(Y_cuped)/Var(Y)  (theory: rho^2)."""
    y = np.asarray(y, float)
    return float(1 - np.var(cuped_adjust(y, x), ddof=1) / np.var(y, ddof=1))


def regression_adjusted(df, metric, covariates, arm_col="arm", treat_label="treatment"):
    """Multi-covariate adjustment. Returns (effect, se, p_value) of the treatment coefficient."""
    X = df[covariates] - df[covariates].mean()
    X.insert(0, "treat", (df[arm_col] == treat_label).astype(int).values)
    fit = sm.OLS(df[metric].values, sm.add_constant(X)).fit(cov_type="HC1")
    return float(fit.params["treat"]), float(fit.bse["treat"]), float(fit.pvalues["treat"])
