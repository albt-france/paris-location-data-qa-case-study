-- 02_source_coverage.sql : pharmacies and schools per source, inside the 11e polygon (PUBLIC DATA).
CREATE OR REPLACE TABLE coverage AS
SELECT theme, source, category, status, count(*) AS n
FROM places WHERE in_11e = 1
GROUP BY ALL ORDER BY theme, source, category, status;

-- Event 9 (false signal): "Overture has far more pharmacies than OSM, so it must contain invented places".
-- Recount step by step with the same area and the same category definition.
CREATE OR REPLACE TABLE false_signal AS
WITH osm AS (SELECT count(*) AS n FROM places
             WHERE in_11e = 1 AND source = 'OSM' AND category = 'pharmacy' AND status = 'open'),
     fin AS (SELECT count(*) AS n FROM places WHERE in_11e = 1 AND source = 'FINESS'),
     ov  AS (SELECT o.*, p.in_11e FROM overture_raw o LEFT JOIN places p ON p.source = 'OVERTURE' AND p.source_id = o.id)
SELECT 1 AS step, 'First count: Overture download box (wider than the 11e), category contains "pharm"' AS definition,
       (SELECT count(*) FROM ov WHERE basic_category ILIKE '%pharm%') AS overture,
       (SELECT n FROM osm) AS osm, (SELECT n FROM fin) AS finess
UNION ALL
SELECT 2, 'Same area: only places inside the 11e polygon',
       (SELECT count(*) FROM ov WHERE basic_category ILIKE '%pharm%' AND in_11e = 1), (SELECT n FROM osm), (SELECT n FROM fin)
UNION ALL
SELECT 3, 'Same category: taxonomy = pharmacy (drugstores removed)',
       (SELECT count(*) FROM ov WHERE taxonomy_primary = 'pharmacy' AND in_11e = 1), (SELECT n FROM osm), (SELECT n FROM fin)
UNION ALL
SELECT 4, 'Same status: open places only (permanently closed and unknown status removed)',
       (SELECT count(*) FROM ov WHERE taxonomy_primary = 'pharmacy' AND in_11e = 1 AND operating_status = 'open'),
       (SELECT n FROM osm), (SELECT n FROM fin)
ORDER BY step;

SELECT * FROM false_signal;
