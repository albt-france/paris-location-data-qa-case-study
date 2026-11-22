# Annotation guidelines v2: checking a local answer

*Scope: answers of a **simulated** local-search assistant (SIMULATED) about pharmacies and schools in Paris 11e, checked against public data (PUBLIC DATA). Desk research only: no field visit.*

Version history: v1 (2026-11-02) had no rule for missing opening hours, for places absent from the official registry, or for position thresholds. v2 (2026-11-12) adds rules 3, 4 and 6 below. With v2, mean Cohen's kappa between the three simulated annotators rose from 0.61 to 0.82 (0.50 to 0.81 on opening-status questions).

## 1. What you receive
One answer = the question type (`find_nearest`, `address_lookup`, `opening_status`, `category_search`), the place category shown, the address and postcode shown, the map pin (lat/lon), and for status questions whether opening hours were given.

## 2. Sources, in the order to use them
| Need | First source | Second source | Notes |
|---|---|---|---|
| Does the address exist? Where is it? | BAN (api-adresse.data.gouv.fr) | OpenStreetMap | Use the BAN `housenumber` result; a `street` result is not enough to judge a pin. |
| Does the pharmacy exist / is it active? | FINESS (official registry) | OpenStreetMap, Overture, SIRENE status | FINESS is an extraction of 2026-05-04: it lags. |
| Does the school exist / is it open? | Education registry (`etat`) | OpenStreetMap, Overture | One building can hold several registry entries (pre-school + elementary). |
| Is it the right kind of place? | Registry category | OSM tags (`amenity=pharmacy`, `dispensing`, `shop=chemist`) | A drugstore or a medical supply shop is not a pharmacy. |
| Is it in the 11e? | BAN city code (75111) | OSM boundary (relation 9533) | Border streets are split between arrondissements by side. |

No source is "the truth": registries are the most reliable reference but lag; open databases are fresher but uneven.

## 3. Decision rules
1. **Exists?** Look for a record of the requested kind within about 40 m of the BAN point of the shown address, in any source. None anywhere, and a web search finds nothing: `major_issue`, code `INVENTED_PLACE`.
2. **Open?** The place is marked closed (Overture `permanently_closed`, OSM `disused:*`, registry `FERME`) and no active registry entry exists at the address: `major_issue`, `CLOSED_PLACE`.
3. **Absent from the registry (v2).** Absence from FINESS or the Education registry is **not proof of error**. Confirmed by a second independent source (another open database, an active SIRENE establishment at the address): `correct`. Only one source: `cannot_verify`. A ceased SIRENE establishment at the address points to a stale record: say so in the comment.
4. **Pin vs address (v2).** Distance between the pin and the BAN geocode of the shown address: < 150 m fine; 150 to 300 m `minor_issue`; 300 m or more `major_issue` (code `POSITION_DRIFT`). Check bis / ter numbers carefully.
5. **Right kind?** Drugstore, medical supply shop, parapharmacy (`dispensing=no`) shown as a pharmacy, or adult / higher education shown as a school: `major_issue`, `WRONG_CATEGORY`.
6. **Opening hours (v2).** Status question answered without hours while the status itself is not contradicted: `minor_issue`, `MISSING_HOURS`. Wrong status is rule 2, not this one.
7. **Area.** Presented as in the 11e but the BAN city code is 75112, 75120, etc.: `minor_issue`, `OUT_OF_AREA` (the user still reaches an open place).
8. **Duplicates.** Two results that are the same place (records a few metres apart, often under two names): `minor_issue`, `DUPLICATE`.
9. **Several problems:** report the most severe verdict and its code. **Never guess:** when sources disagree and nothing settles it, answer `cannot_verify` and write which sources disagree.

## 4. Ten anonymised examples (ids from the workbook, names removed)
| # | Answer | What was shown | Evidence | Verdict |
|---|---|---|---|---|
| 1 | A0001 | Pharmacy "open now", hours given, address in 75011 | BAN housenumber 3 m from pin; FINESS + OSM + Overture at the address | `correct` |
| 2 | A0032 | Pharmacy in a category search | BAN point found; no pharmacy in any source within 40 m | `major_issue` INVENTED_PLACE |
| 3 | A0013 | Nearest pharmacy, "open" | Only an Overture record, `permanently_closed`; no FINESS entry | `major_issue` CLOSED_PLACE |
| 4 | A0003 | Pharmacy in a category search | Only record at the address is an Overture drugstore | `major_issue` WRONG_CATEGORY |
| 5 | A0042 | Nearest pharmacy "in 75011" | BAN city code 75120: the pharmacy is across the border street | `minor_issue` OUT_OF_AREA |
| 6 | A0017 | Pharmacy address with a "bis" number | Pin 164 m from the BAN geocode | `minor_issue` POSITION_DRIFT |
| 7 | A0096 | School address with a "bis" number | Pin 375 m from the BAN geocode | `major_issue` POSITION_DRIFT |
| 8 | A0040 | Two pharmacies listed | Both results resolve to the same pharmacy (OSM and Overture records metres apart) | `minor_issue` DUPLICATE |
| 9 | A0023 | Pharmacy "open now", no hours | Pharmacy active in FINESS, OSM, Overture | `minor_issue` MISSING_HOURS |
| 10 | A0028 | Pharmacy "open now" | Only one Overture record; not in FINESS; no second source | `cannot_verify` |

## 5. Three examples worked step by step

**A0013, closed place.** (1) BAN: the shown address is a housenumber result in 75111, 0.4 m from the pin: position fine. (2) Records within 40 m: one Overture record, category pharmacy, `operating_status = permanently_closed`. (3) FINESS: no active pharmacy at the address; OSM: nothing. (4) Rule 2 applies: the user is sent to a closed pharmacy. Verdict `major_issue`, code `CLOSED_PLACE`. Comment: "closed per Overture, absent from FINESS".

**A0042, out of area.** (1) BAN: housenumber found, pin 4.6 m away. (2) Records: FINESS and Overture pharmacy at the address, active: the place exists and is open. (3) BAN city code 75120, while the answer says 75011: the pharmacy is on the 20e side of a border boulevard. (4) Rule 7: `minor_issue`, `OUT_OF_AREA`. Not major: the user still reaches an open pharmacy a few steps outside the district.

**A0028, cannot verify.** (1) BAN: housenumber, pin 2.2 m away. (2) Records: one Overture pharmacy; no FINESS entry, no OSM object, no active SIRENE establishment within 50 m. (3) Rule 3: absent from the registry is not proof of error, but there is no second source. (4) Verdict `cannot_verify`. Comment: "Overture only; FINESS extract is 2026-05-04; needs a web check (opening notice, pharmacy order listing)". Answering `major_issue` here would be the v1 mistake.

## 6. Comment template
`<code> | evidence: <sources at the address> | BAN: <type>, <distance> m, city code <code> | note: <what disagrees>`
