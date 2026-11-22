# Checklist per task: one answer in under 2 minutes

*Simulated median time per task: 79 s with guidelines v1, 65 s with v2 (SIMULATED annotators; your own time is the one that counts).*

1. **Read the answer (10 s).** Question type, category shown, address and postcode, pin, hours given or not.
2. **Geocode the address (20 s).** BAN search: is it a `housenumber` result? City code 75111? Distance pin vs BAN point: < 150 m ok, 150-300 m minor, >= 300 m major.
3. **Find the place (30 s).** Around the BAN point (about 40 m): registry (FINESS for pharmacies, Education registry for schools), then OpenStreetMap, then Overture. Read the name and the category (`dispensing=no`, `shop=chemist` = not a pharmacy).
4. **Check the status (20 s).** Closed in a source and no active registry entry: major. Absent from the registry only: look for a second source; none: `cannot_verify`.
5. **Check the question itself (10 s).** Nearest really the nearest? Inside the 11e? Same place listed twice? Hours missing on a status question?
6. **Decide and write (20 s).** Most severe verdict + code + one-line comment: `<code> | evidence: <sources> | BAN: <type>, <m>, <city code> | note`. If you hesitate for more than 30 s between two verdicts, re-read the rubric rule; if sources truly disagree, `cannot_verify`.
