-- 06_assistant_errors.sql : automatic checks on the 600 SIMULATED assistant answers.
-- Each shown address is geocoded with the BAN, then compared with the places of every source.
CREATE OR REPLACE TABLE answer_geo AS
SELECT a.*, g.ban_lat, g.ban_lon, g.ban_citycode, g.ban_score,
       round(hav(a.shown_lat::DOUBLE, a.shown_lon::DOUBLE, g.ban_lat, g.ban_lon), 1) AS pin_vs_ban_m
FROM answers a LEFT JOIN ban_geocodes g ON g.street = a.shown_address;

-- Records of the same theme within 40 m of the BAN point of the shown address
CREATE OR REPLACE TABLE answer_evidence AS
SELECT g.answer_id,
       count(p.place_id) AS records_found,
       bool_or(p.source IN ('FINESS', 'EDU')) AS in_registry,
       bool_or(p.status = 'open') AS any_open,
       bool_or(p.status = 'closed') AS any_closed,
       bool_or(p.category IN ('pharmacy', 'school', 'secondary_school') AND p.status <> 'closed') AS right_category,
       string_agg(DISTINCT p.source, '+' ORDER BY p.source) AS sources,
       string_agg(DISTINCT p.category, '+' ORDER BY p.category) AS categories,
       min(CASE WHEN p.source = 'OSM' THEN p.source_id END) AS osm_ref
FROM answer_geo g
LEFT JOIN places p ON p.theme = g.theme AND g.ban_lat IS NOT NULL
      AND abs(p.lat - g.ban_lat) < 0.0004 AND hav(p.lat, p.lon, g.ban_lat, g.ban_lon) <= 40
GROUP BY g.answer_id;

CREATE OR REPLACE TABLE assistant_checks AS
SELECT g.answer_id, g.query_type, g.theme, g.asked_on, g.guidelines_version, g.place_ref, g.place_ref_2,
       g.shown_address, g.shown_postcode, g.shown_lat, g.shown_lon, g.shown_status, g.shown_category, g.shown_hours,
       g.ban_citycode, g.pin_vs_ban_m, e.records_found, e.sources, e.categories, e.in_registry, e.osm_ref,
       e.records_found = 0                                                 AS chk_not_found,
       coalesce(e.any_closed AND NOT e.in_registry AND NOT e.right_category, false)
         OR coalesce(e.any_closed AND NOT e.any_open, false)               AS chk_closed,
       coalesce(e.records_found > 0 AND NOT e.right_category AND NOT e.any_closed, false) AS chk_category,
       coalesce(g.ban_citycode <> '75111', false)                          AS chk_boundary,
       coalesce(g.pin_vs_ban_m >= 150, false)                              AS chk_drift,
       coalesce(g.place_ref_2 IS NOT NULL AND g.place_ref_2 <> '' AND
         (SELECT hav(p1.lat, p1.lon, p2.lat, p2.lon) FROM places p1, places p2
          WHERE p1.place_id = g.place_ref AND p2.place_id = g.place_ref_2) <= 40, false) AS chk_duplicate,
       (g.query_type = 'opening_status' AND g.shown_hours = 'no')           AS chk_missing_hours,
       coalesce(e.records_found > 0 AND NOT e.in_registry, false)          AS chk_not_in_registry
FROM answer_geo g JOIN answer_evidence e USING (answer_id);

ALTER TABLE assistant_checks ADD COLUMN auto_code VARCHAR;
UPDATE assistant_checks SET auto_code = CASE
    WHEN chk_not_found THEN 'NOT_FOUND'
    WHEN chk_closed THEN 'CLOSED_PLACE'
    WHEN chk_category THEN 'WRONG_CATEGORY'
    WHEN chk_boundary THEN 'OUT_OF_AREA'
    WHEN chk_drift THEN 'POSITION_DRIFT'
    WHEN chk_duplicate THEN 'DUPLICATE'
    WHEN chk_missing_hours THEN 'MISSING_HOURS'
    WHEN chk_not_in_registry THEN 'NOT_IN_REGISTRY'
    ELSE 'PASS' END;

-- Consensus verdict of the 3 simulated annotators (majority; ties -> needs adjudication)
CREATE OR REPLACE TABLE consensus AS
SELECT answer_id,
       CASE WHEN max(c) >= 2 THEN arg_max(verdict, c) ELSE 'needs_adjudication' END AS consensus_verdict,
       max(c) AS votes
FROM (SELECT answer_id, verdict, count(*) AS c FROM annotations GROUP BY ALL) GROUP BY answer_id ORDER BY answer_id;

CREATE OR REPLACE TABLE error_rates AS
SELECT query_type, count(*) AS answers,
       sum(CASE WHEN auto_code NOT IN ('PASS', 'NOT_IN_REGISTRY') THEN 1 ELSE 0 END) AS flagged,
       round(100.0 * sum(CASE WHEN auto_code NOT IN ('PASS', 'NOT_IN_REGISTRY') THEN 1 ELSE 0 END) / count(*), 1) AS pct_flagged
FROM assistant_checks GROUP BY ALL ORDER BY query_type;

CREATE OR REPLACE TABLE error_codes AS
SELECT auto_code, query_type, count(*) AS n FROM assistant_checks GROUP BY ALL ORDER BY auto_code, query_type;

SELECT auto_code, count(*) AS n, round(100.0 * count(*) / 600, 1) AS pct FROM assistant_checks GROUP BY ALL ORDER BY n DESC;
