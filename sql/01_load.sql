-- 01_load.sql : load public (PUBLIC DATA) and simulated (SIMULATED) tables into DuckDB.
-- Distances use a haversine macro (metres) so the spatial extension is not required.
CREATE OR REPLACE MACRO hav(lat1, lon1, lat2, lon2) AS
    2 * 6371000 * asin(sqrt(pow(sin(radians(lat2 - lat1) / 2), 2)
      + cos(radians(lat1)) * cos(radians(lat2)) * pow(sin(radians(lon2 - lon1) / 2), 2)));

-- PUBLIC DATA: normalised places (OSM, Overture, FINESS, Education registry) + BAN geocode of their address.
-- name / name_norm are only used for matching inside DuckDB and are never exported.
CREATE OR REPLACE TABLE places AS
SELECT * FROM read_csv('data/raw/norm_places.csv', header = true, auto_detect = true,
                       types = {'source_id': 'VARCHAR', 'postcode': 'VARCHAR', 'ban_citycode': 'VARCHAR'});

CREATE OR REPLACE TABLE overture_raw AS
SELECT id, lon, lat, basic_category, operating_status,
       json_extract_string(taxonomy_json, '$.primary') AS taxonomy_primary,
       json_extract_string(sources_json, '$[0].license') AS licence
FROM 'data/raw/overture_places.parquet';

CREATE OR REPLACE TABLE sirene AS          -- secondary check: SIRET, activity, status, position only
SELECT siret::VARCHAR AS siret, activite, etat, lat, lon, date_creation, date_fermeture
FROM read_csv('data/raw/sirene_4773Z.csv', header = true, auto_detect = true) WHERE lat IS NOT NULL;

CREATE OR REPLACE TABLE ban_geocodes AS
SELECT * FROM read_csv('data/processed/ban_geocodes.csv', header = true, types = {'ban_citycode': 'VARCHAR'});

-- SIMULATED
CREATE OR REPLACE TABLE answers AS
SELECT * FROM read_csv('data/processed/assistant_answers.csv', header = true, all_varchar = true);
CREATE OR REPLACE TABLE annotations AS
SELECT * FROM read_csv('data/processed/annotations.csv', header = true, auto_detect = true);
CREATE OR REPLACE TABLE guidelines_versions AS
SELECT * FROM read_csv('data/processed/guidelines_versions.csv', header = true);

SELECT 'places' AS t, count(*) AS n FROM places UNION ALL
SELECT 'overture_raw', count(*) FROM overture_raw UNION ALL
SELECT 'sirene', count(*) FROM sirene UNION ALL
SELECT 'answers', count(*) FROM answers UNION ALL
SELECT 'annotations', count(*) FROM annotations;
