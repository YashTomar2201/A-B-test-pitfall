-- CUPED on Hillstrom: adjust 2008-era post-campaign spend using pre-period spend (history).
-- theta = cov(Y, X) / var(X) is computed on both arms pooled; adjusted Y = Y - theta * (X - mean(X)).
WITH exp AS (
    SELECT user_id, segment AS arm, spend AS y, history AS x
    FROM raw.hillstrom
    WHERE segment IN ('No E-Mail', 'Womens E-Mail')
),
theta AS (
    SELECT covar_samp(y, x) / var_samp(x) AS theta, avg(x) AS x_bar FROM exp
)
SELECT
    arm,
    count(*)                                               AS users,
    avg(y)                                                 AS mean_raw,
    var_samp(y)                                            AS var_raw,
    avg(y - theta * (x - x_bar))                           AS mean_cuped,
    var_samp(y - theta * (x - x_bar))                      AS var_cuped,
    1 - var_samp(y - theta * (x - x_bar)) / var_samp(y)    AS variance_reduction
FROM exp, theta
GROUP BY arm
ORDER BY arm;
