# Source reliability: strengths, weaknesses, freshness, licence

*All sources read on 2026-11-22. Area: Paris 11e (OSM relation 9533, INSEE 75111). Desk research only.*

| Source | Type | Freshness | Strengths | Weaknesses (seen in this study) | Licence |
|---|---|---|---|---|---|
| **FINESS**, health establishments (Ministry of Health, data.gouv.fr) | Official registry | Extraction of 2026-05-04 (about 6 months old) | Authoritative list of dispensing pharmacies (category 620); coordinates consistent with the BAN (median 0 m) | Lags behind openings and closures; two record types in one file (`structureet`, `geolocalisation`); Lambert 93 coordinates; contains phone numbers (dropped here) | Licence Ouverte (Etalab) |
| **Education registry** (`fr-en-annuaire-education`) | Official registry | Updated continuously | Status field `etat`; school type; coordinates consistent with the BAN (median 0 m) | One building can hold several entries (pre-school, elementary); 12 of 96 entries are not schools (orientation centres, etc.) | Licence Ouverte v2.0 (Etalab), per the dataset metadata |
| **BAN**, address geocoder (api-adresse.data.gouv.fr) | Official address reference | Continuous | House-number level positions; city code tells the arrondissement; batch CSV endpoint (1 upload for 1,000+ addresses) | Without a postcode, an address can match another town (fixed by adding "Paris") | Licence Ouverte |
| **OpenStreetMap** (Overpass API) | Open, community | Continuous | 95% of FINESS pharmacies found; useful tags (`dispensing`, `disused:*`, `opening_hours`) | Only 41 of 188 OSM pharmacy and school objects carry a full address; pins a few metres off the BAN (median 6.5 m, 90th percentile 40 m) | ODbL, © OpenStreetMap contributors |
| **Overture Maps places** (release 2026-11-18.0) | Open, aggregated | Monthly releases | `confidence` and `operating_status`; 90% of FINESS pharmacies found | Broad categories (`pharmacy_and_drug_store`); status unknown for most schools (54 of 56); 9 pins >= 150 m from the BAN; same place under different names in OSM; schema changed (no more `categories.primary`, now `basic_category` + `taxonomy`) | Per source record: CDLA-Permissive-2.0 (most records), Apache-2.0 (Foursquare), CC0-1.0 (AllThePlaces); licence as stated on the provider's page, checked on 2026-11-22: https://docs.overturemaps.org/attribution/ |
| **SIRENE** (recherche-entreprises.api.gouv.fr) | Official business register | Continuous | Administrative status (active / ceased) and creation date | Activity code 47.73Z is wider than dispensing pharmacies; returns owners' names for sole traders (never stored here); 10 result pages read (269 establishments) | Licence Ouverte |

## Rules of thumb
1. Registry first for existence, but **absence from a registry is not proof** (lag).
2. Open databases for freshness and detail, but confirm with a second source.
3. Always compare like with like: same area, same category definition, same status filter (see the false signal in `data_issues_log.md`).

## Not used
Google Maps and Apple Maps (no open API without a key, restrictive terms); no scraping of business websites.
