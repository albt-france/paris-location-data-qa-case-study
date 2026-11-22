# Error taxonomy for AI-generated local answers

*Counts: 600 SIMULATED answers checked against PUBLIC DATA (Paris 11e). Automatic code = first failing check, in the priority order below.*

| Code | Definition | Automatic check | Severity | Answers (auto) |
|---|---|---|---|---|
| `INVENTED_PLACE` | Cites a place that exists in no source (hallucination). Automatic flag: `NOT_FOUND`. | No record of the requested kind within 40 m of the BAN point of the shown address, in any of the 4 sources | major | 16 |
| `CLOSED_PLACE` | Recommends a place that has closed | Source status closed (Overture `operating_status`, OSM `disused:*`) and no active registry entry at the address | major | 37 |
| `WRONG_CATEGORY` | Right address, wrong kind (drugstore, medical supply, parapharmacy shown as a pharmacy; adult education shown as a school) | Records found at the address, none of the requested category | major | 24 |
| `OUT_OF_AREA` | Presented as in the 11e, located in a neighbouring arrondissement | BAN city code is not 75111 | minor | 24 |
| `POSITION_DRIFT` | Pin far from the address it shows (often bis / ter numbers) | Pin vs BAN geocode >= 150 m | minor (150-300 m), major (>= 300 m) | 24 |
| `DUPLICATE` | Same place listed twice | The two cited records are <= 40 m apart | minor | 18 |
| `MISSING_HOURS` | Status answer without opening hours | `opening_status` question and no hours shown | minor | 40 |
| `NOT_IN_REGISTRY` | *Not an error by itself*: absent from the official registry | No registry record at the address, then second-source check | correct or cannot_verify | 18 |
| `PASS` | All automatic checks passed | | correct (after reading the name) | 399 |

## How well do the automatic checks work? (SIMULATED answer key, opened after the checks ran)
- 182 of the 184 answers with a planted issue got the right code.
- Missed: 2 invented places. One shown address happens to host a real pharmacy (the check passes; only reading the name against the evidence catches it). The other sits next to a closed pharmacy record and was coded `CLOSED_PLACE` (still `major_issue`).
- 0 false alarms on the 398 clean answers.
- Caveat: the errors were planted by the same person who wrote the checks, so this recall is optimistic. Real answers would mix errors and show cases the taxonomy does not cover yet (wrong name, wrong phone, wrong hours).

## Severity logic
- **major**: the user is sent to a place that cannot serve them (closed, non-existent, wrong kind) or to the wrong block.
- **minor**: the user still reaches a valid place, with friction.
- **cannot_verify**: desk evidence is not enough; never guess.
