-- 04_status_checks.sql : closed places, places absent from the official registry, second-source check.
CREATE OR REPLACE TABLE status_by_source AS
SELECT theme, source, status, count(*) AS n
FROM places WHERE in_11e = 1 GROUP BY ALL ORDER BY theme, source, status;

-- Event 7 (real data-quality issue): FINESS is an extraction of 2026-05-04 (about 6 months old).
-- An open-data pharmacy with no registry counterpart is NOT automatically false: look for a second source.
CREATE OR REPLACE TABLE not_in_registry AS
WITH od AS (
  SELECT p.* FROM places p
  WHERE p.in_11e = 1 AND p.theme = 'pharmacy' AND p.category = 'pharmacy' AND p.status = 'open'
    AND p.source IN ('OSM', 'OVERTURE')
    AND NOT EXISTS (SELECT 1 FROM matches m WHERE m.place_id = p.place_id AND m.other_source = 'FINESS'))
SELECT od.place_id, od.source, od.confidence,
       (SELECT round(min(hav(od.lat, od.lon, f.lat, f.lon))) FROM places f WHERE f.source = 'FINESS') AS nearest_finess_m,
       EXISTS (SELECT 1 FROM matches m WHERE m.place_id = od.place_id
               AND m.other_source IN ('OSM', 'OVERTURE')) AS other_open_source,
       (SELECT round(min(hav(od.lat, od.lon, s.lat, s.lon))) FROM sirene s WHERE s.etat = 'A') AS nearest_sirene_active_m,
       (SELECT round(min(hav(od.lat, od.lon, s.lat, s.lon))) FROM sirene s WHERE s.etat = 'F') AS nearest_sirene_ceased_m,
       CASE
         WHEN EXISTS (SELECT 1 FROM matches m WHERE m.place_id = od.place_id AND m.other_source IN ('OSM', 'OVERTURE'))
           OR (SELECT min(hav(od.lat, od.lon, s.lat, s.lon)) FROM sirene s WHERE s.etat = 'A') <= 50
           THEN 'confirmed by a second source'
         WHEN (SELECT min(hav(od.lat, od.lon, s.lat, s.lon)) FROM sirene s WHERE s.etat = 'F') <= 50
           THEN 'likely stale: ceased SIRENE establishment nearby'
         WHEN (SELECT min(hav(od.lat, od.lon, f.lat, f.lon)) FROM places f WHERE f.source = 'FINESS') <= 120
           THEN 'probable pin offset of a registry pharmacy'
         ELSE 'cannot verify (desk research only)'
       END AS assessment
FROM od;

-- Registry pharmacies that the open sources miss
CREATE OR REPLACE TABLE registry_missing_in_open AS
SELECT p.place_id,
       EXISTS (SELECT 1 FROM matches m WHERE m.place_id = p.place_id AND m.other_source = 'OSM') AS in_osm,
       EXISTS (SELECT 1 FROM matches m WHERE m.place_id = p.place_id AND m.other_source = 'OVERTURE') AS in_overture,
       p.date_open
FROM places p WHERE p.source = 'FINESS' AND p.in_11e = 1;

SELECT assessment, count(*) FROM not_in_registry GROUP BY ALL;
SELECT in_osm, in_overture, count(*) FROM registry_missing_in_open GROUP BY ALL;
