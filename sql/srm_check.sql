-- Sample ratio mismatch check in pure SQL (chi-square goodness of fit, df = 1).
-- Criteo's DOCUMENTED split is 85% treatment / 15% control, NOT 50/50.
-- 10.828 is the chi-square critical value for p = 0.001 with df = 1.
WITH params AS (SELECT 0.85::DOUBLE AS expected_treat_share),
counts AS (
    SELECT sum(treatment)::DOUBLE AS n_t, sum(1 - treatment)::DOUBLE AS n_c, count(*)::DOUBLE AS n
    FROM raw.criteo
),
chi AS (
    SELECT n_t, n_c, n, expected_treat_share AS e,
           power(n_t - n * expected_treat_share, 2) / (n * expected_treat_share)
         + power(n_c - n * (1 - expected_treat_share), 2) / (n * (1 - expected_treat_share)) AS chi2
    FROM counts, params
)
SELECT n_t, n_c, n_t / n AS observed_treat_share, e AS expected_treat_share, chi2,
       chi2 > 10.828 AS srm_flag
FROM chi;
