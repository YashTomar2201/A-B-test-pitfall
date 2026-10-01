# Methodology

Technical notes for each method: formula, assumptions, when it breaks, and the reference. Code lives in `src/abtest/`.

## Core tests (`analyze/tests.py`)
| Method | Formula / idea | Assumptions | Breaks when |
|---|---|---|---|
| Two-proportion z-test | z = (p_b - p_a) / sqrt(p(1-p)(1/n_a + 1/n_b)), pooled p for the test, unpooled SE for the CI | Independent users, large counts | Rare events with small n; non-independent units |
| Welch t-test | Unequal-variance t with Welch-Satterthwaite dof | Roughly normal means | Very heavy tails with small n |
| Bootstrap CI | Percentile CI of the resampled difference in means | iid resampling units | Units are not independent (resample the randomisation unit) |
| Delta method for ratios | Var(R) ~ (Var(Y)/mu_x^2 - 2 mu_y Cov/mu_x^3 + mu_y^2 Var(X)/mu_x^4)/n, one row per user | Large n | Tiny samples |
| Sample ratio mismatch | Chi-square goodness of fit on arm counts | Documented split is correct | Split documented incorrectly (check the *expected* ratio) |

## Power (`analyze/power.py`)
Normal approximation: n per arm = (z_{1-a/2} + z_{power})^2 (p1(1-p1) + p2(1-p2)) / (p2 - p1)^2. Cross-checked against statsmodels in `tests/test_stats.py`.

## Simulation (`simulate/`)
User-level engine with a latent engagement factor, a solved logit intercept (so the average rate equals `base_cr`), log-normal revenue, an optional pre-period covariate with chosen correlation, and switches for each pitfall. A binomial-count simulator reproduces the same z-test statistics ~100x faster. Validation protocol: 1,000+ A/A tests (rate 5% +/- 1.5%, flat p-values by a KS test), and known-effect recovery with 95% CI coverage (`tests/test_simulator.py`, `scripts/run_validation.py`).

## Sequential testing (`analyze/sequential.py`)
- **Group sequential, O'Brien-Fleming**: reject at look k if |z_k| > c * sqrt(K/k). The constant c is calibrated by simulating the null random walk so the overall false positive rate equals alpha. Requires the number of looks to be planned.
- **mSPRT** (Johari, Pekelis & Walsh): with a N(0, tau^2) mixing prior on the effect, the likelihood ratio is sqrt(V/(V+tau^2)) * exp(tau^2 theta_hat^2 / (2V(V+tau^2))); the always-valid p-value is the running minimum of 1/LR. Valid under continuous monitoring, therefore conservative with a few discrete looks. Sensitive to tau.

## Winner's curse (Gelman & Carlin 2014)
Type M error: average |estimate| / true effect among significant results. Type S error: share of significant results with the wrong sign.

## Multiple testing (`pitfalls/multiple_testing.py`)
Holm step-down controls the family-wise error rate; Benjamini-Hochberg controls the false discovery rate. Implemented vectorised and checked to hold 5% with correlated metrics (rho = 0.3).

## Novelty trend
Weighted least squares of the daily effect on the day, weights 1/SE^2. Flag: one-sided p < 0.01 *and* first-half effect > second-half effect.

## Heavy tails
Winsorise at the **pooled** 99th percentile (per-arm caps bias the comparison). This estimates the effect on capped revenue, not true revenue. CUPED and the bootstrap are compared on the same simulated data.

## CUPED and covariate adjustment (`analyze/cuped.py`; Deng et al. 2013)
Y_cuped = Y - theta (X - mean(X)), theta = Cov(Y, X)/Var(X) on both arms pooled. Variance reduction = rho^2. For several covariates and unbalanced arms use a joint regression of Y on the treatment indicator and centred covariates (ANCOVA, HC1 standard errors); estimating theta without the treatment term is invalid when arms differ on the covariates (found on Criteo, see decision log).

## Health checker (`diagnose/checker.py`)
Seven checks: sample ratio (p < 0.001 = red), peeking (process flag), power (achieved MDE vs planned), multiple comparisons (Holm), novelty trend, outlier sensitivity (does significance flip after winsorising?), and covariate balance (max standardized difference vs a Bonferroni critical value at p = 0.001 = red). Verdict: red -> don't trust; yellow -> investigate; otherwise ship only if the primary metric is significant and positive.

## Audit (`audit/portfolio.py`)
Scenario mix and economics in `config/audit_portfolio.yaml`. The naive analyst looks daily and stops at the first positive p < 0.05, and also ships if revenue or any of 5 segments is significant. The rigorous analyst uses one primary metric at a fixed horizon and ships only on a clean health check. Every decision is scored against the known truth.

## References
- Kohavi, Tang & Xu (2020), *Trustworthy Online Controlled Experiments*.
- Deng, Xu, Kohavi & Walker (2013), CUPED.
- Johari, Pekelis & Walsh, *Always Valid Inference*.
- Fabijan et al. (2019), *Diagnosing Sample Ratio Mismatch in Online Controlled Experiments*.
- Gelman & Carlin (2014), *Beyond Power Calculations*.
- Deng, Lu & Litz (2017), *Trustworthy Analysis of Online A/B Tests*.
- Diemert et al. (2018), *A Large Scale Benchmark for Uplift Modeling* (Criteo dataset).
