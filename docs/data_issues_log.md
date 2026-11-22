# Data issues log

*PUBLIC DATA unless stated. Paris 11e, read on 2026-11-22.*

| # | Issue | Evidence | Impact on QA | Handling |
|---|---|---|---|---|
| D1 | **Same pharmacy twice across sources** (OSM vs Overture) | 22 OSM–Overture pairs of pharmacies <= 30 m apart (median 6.4 m) with dissimilar names (Jaro-Winkler < 0.85) | A merge on names would count 22 extra pharmacies; an assistant can list the same place twice | Match on distance first, then name: <= 30 m any name, or <= 120 m with name similarity >= 0.85 (`sql/03_matching.sql`) |
| D2 | **Registry lag** | FINESS extraction 2026-05-04. 13 open-data pharmacies have no FINESS match: 6 probable pin offsets of a registry pharmacy (63-102 m), 2 confirmed by a second source, 1 likely stale (ceased SIRENE establishment 27 m away), 4 cannot be verified from the desk. SIRENE shows no 47.73Z establishment created or ceased in the 11e after 2026-05-04 | "Absent from the registry" would wrongly be read as "invented" | Rule 3 of the guidelines: second source or `cannot_verify` (`sql/04_status_checks.sql`) |
| D3 | **Overture schema change** | Release 2026-11-18.0: no `categories.primary`; `basic_category` and `taxonomy` instead | Old queries fail or silently return nothing | Read the schema before each release; filter on `basic_category` + `taxonomy.primary` |
| D4 | **Broad Overture category** | `pharmacy_and_drug_store` mixes pharmacies (81) and drugstores (3) in the 11e | Drugstores counted as pharmacies | Use `taxonomy.primary = 'pharmacy'` |
| D5 | **Overture status unknown** | 18 of 84 pharmacy records and 54 of 56 school records have no `operating_status` | Cannot use Overture alone to say "open" | Second source |
| D6 | **Positions off the address** | Overture: 9 pins >= 150 m from the BAN geocode; OSM: 90th percentile 40 m | Wrong pins mislead "nearest" answers | Distance check against the BAN (`sql/05_geocode_drift.sql`) |
| D7 | **Addresses without postcode** | First BAN batch matched some OSM addresses to other French towns (up to 500 km) | False drift | Add "Paris" to the query and drop results outside city codes 751xx |
| D8 | **School registry granularity** | One building, several entries (pre-school + elementary); only 62% of registry schools match an OSM school | Low match rate is not low quality | Compare at building level; do not report "missing schools" |
| D9 | **FALSE SIGNAL (not a defect)** | First count: 300 Overture "pharm" records vs 56 OSM pharmacies (5x). Same polygon: 84; pharmacy taxonomy only: 81; open only: **60** vs OSM 56 and FINESS 59 | Would have led to "Overture invents pharmacies" | Not reported as an issue; recount shown in `sql/02_source_coverage.sql` and the notebook |
| D10 | Overpass 502 errors | Schools query failed twice on the first run | None (cached later) | Stopped after one retry, re-ran once later; no loop |
