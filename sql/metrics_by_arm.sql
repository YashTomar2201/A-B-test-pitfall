-- Per-arm metrics for the Criteo experiment (treatment = 1 is the ad-exposed arm).
SELECT
    treatment                       AS arm,
    count(*)                        AS users,
    avg(visit)                      AS visit_rate,
    avg(conversion)                 AS conversion_rate,
    var_samp(conversion)            AS conversion_var
FROM raw.criteo
GROUP BY treatment
ORDER BY arm;
