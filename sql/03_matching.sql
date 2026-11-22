-- 03_matching.sql : match places across sources by distance + name similarity (PUBLIC DATA).
-- Rule: same theme, and (distance <= 30 m) or (distance <= 120 m and Jaro-Winkler name similarity >= 0.85).
CREATE OR REPLACE TABLE candidate_pairs AS
SELECT a.place_id, a.theme, a.source, b.place_id AS other_id, b.source AS other_source,
       round(hav(a.lat, a.lon, b.lat, b.lon), 1) AS dist_m,
       round(CASE WHEN a.name_norm IS NULL OR b.name_norm IS NULL THEN 0
                  ELSE jaro_winkler_similarity(a.name_norm, b.name_norm) END, 3) AS name_sim
FROM places a JOIN places b
  ON a.theme = b.theme AND a.source <> b.source
 AND abs(a.lat - b.lat) < 0.0011 AND abs(a.lon - b.lon) < 0.0017          -- ~120 m pre-filter
WHERE hav(a.lat, a.lon, b.lat, b.lon) <= 120;

CREATE OR REPLACE TABLE matches AS
SELECT * EXCLUDE (rk) FROM (
  SELECT *, CASE WHEN dist_m <= 30 THEN 'distance' ELSE 'distance+name' END AS rule,
         row_number() OVER (PARTITION BY place_id, other_source ORDER BY dist_m) AS rk
  FROM candidate_pairs WHERE dist_m <= 30 OR name_sim >= 0.85)
WHERE rk = 1;

-- How many records of each source (11e, not closed, main category) find a counterpart in each other source
CREATE OR REPLACE TABLE matching_summary AS
SELECT p.theme, p.source, o.other_source, count(DISTINCT p.place_id) AS records,
       count(DISTINCT m.place_id) AS matched,
       round(100.0 * count(DISTINCT m.place_id) / count(DISTINCT p.place_id), 1) AS pct_matched,
       round(median(m.dist_m), 1) AS median_dist_m
FROM places p
CROSS JOIN (SELECT DISTINCT source AS other_source FROM places) o
LEFT JOIN matches m ON m.place_id = p.place_id AND m.other_source = o.other_source
WHERE p.in_11e = 1 AND p.status <> 'closed' AND p.category IN ('pharmacy', 'school', 'secondary_school')
  AND o.other_source <> p.source
  AND NOT (p.theme = 'pharmacy' AND o.other_source = 'EDU') AND NOT (p.theme = 'school' AND o.other_source = 'FINESS')
GROUP BY ALL ORDER BY p.theme, p.source, o.other_source;

-- Event 6 (real data-quality issue): the same pharmacy twice -> cross-source pairs that a naive merge
-- would keep as two places: matched by distance but with different names, or same name 20-120 m apart.
CREATE OR REPLACE TABLE cross_source_duplicates AS
SELECT place_id, other_id, theme, source, other_source, dist_m, name_sim,
       CASE WHEN name_sim < 0.85 THEN 'different name, <= 30 m' ELSE 'same name, 20-120 m apart' END AS pattern
FROM matches
WHERE source < other_source AND source IN ('OSM', 'OVERTURE') AND other_source IN ('OSM', 'OVERTURE')
  AND theme = 'pharmacy' AND (name_sim < 0.85 OR dist_m > 20);

-- Duplicates inside one source: two records <= 30 m apart with similar names
CREATE OR REPLACE TABLE within_source_duplicates AS
SELECT a.source, a.theme, a.place_id, b.place_id AS other_id,
       round(hav(a.lat, a.lon, b.lat, b.lon), 1) AS dist_m,
       round(jaro_winkler_similarity(coalesce(a.name_norm, ''), coalesce(b.name_norm, '')), 3) AS name_sim
FROM places a JOIN places b ON a.source = b.source AND a.theme = b.theme AND a.place_id < b.place_id
WHERE a.in_11e = 1 AND hav(a.lat, a.lon, b.lat, b.lon) <= 30
  AND jaro_winkler_similarity(coalesce(a.name_norm, ''), coalesce(b.name_norm, '')) >= 0.9;

SELECT * FROM matching_summary;
SELECT pattern, count(*) FROM cross_source_duplicates GROUP BY ALL;
SELECT source, theme, count(*) FROM within_source_duplicates GROUP BY ALL;
