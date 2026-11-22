-- 05_geocode_drift.sql : distance (m) between each source's pin and the BAN geocode of its address.
CREATE OR REPLACE TABLE drift AS
SELECT place_id, theme, source, bis_ter, ban_score, ban_type, ban_dist_m,
       CASE WHEN ban_dist_m < 10 THEN '1: <10 m' WHEN ban_dist_m < 30 THEN '2: 10-30 m'
            WHEN ban_dist_m < 75 THEN '3: 30-75 m' WHEN ban_dist_m < 150 THEN '4: 75-150 m'
            ELSE '5: >=150 m' END AS band
FROM places WHERE ban_dist_m IS NOT NULL AND ban_type = 'housenumber';

CREATE OR REPLACE TABLE drift_summary AS
SELECT source, count(*) AS geocoded,
       round(median(ban_dist_m), 1) AS median_m,
       round(quantile_cont(ban_dist_m, 0.9), 1) AS p90_m,
       sum(CASE WHEN ban_dist_m >= 150 THEN 1 ELSE 0 END) AS over_150m,
       sum(bis_ter) AS bis_ter_addresses,
       sum(CASE WHEN bis_ter = 1 AND ban_dist_m >= 150 THEN 1 ELSE 0 END) AS bis_ter_over_150m
FROM drift GROUP BY source ORDER BY source;

CREATE OR REPLACE TABLE drift_bands AS
SELECT source, band, count(*) AS n FROM drift GROUP BY ALL ORDER BY source, band;

SELECT * FROM drift_summary;
