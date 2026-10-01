-- Two-proportion z-test on Criteo conversion, written entirely in SQL.
-- Unequal arms are fine: the pooled SE uses 1/n_c + 1/n_t.
WITH a AS (
    SELECT
        sum(CASE WHEN treatment = 0 THEN conversion END)::DOUBLE AS conv_c,
        sum(CASE WHEN treatment = 0 THEN 1 END)::DOUBLE          AS n_c,
        sum(CASE WHEN treatment = 1 THEN conversion END)::DOUBLE AS conv_t,
        sum(CASE WHEN treatment = 1 THEN 1 END)::DOUBLE          AS n_t
    FROM raw.criteo
),
b AS (
    SELECT *, conv_c / n_c AS p_c, conv_t / n_t AS p_t,
           (conv_c + conv_t) / (n_c + n_t) AS p_pool
    FROM a
)
SELECT p_c, p_t, p_t - p_c AS diff, (p_t - p_c) / p_c AS rel_lift,
       (p_t - p_c) / sqrt(p_pool * (1 - p_pool) * (1 / n_c + 1 / n_t)) AS z,
       abs((p_t - p_c) / sqrt(p_pool * (1 - p_pool) * (1 / n_c + 1 / n_t))) > 1.96 AS significant
FROM b;
