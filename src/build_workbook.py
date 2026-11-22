"""Build qa/location_qa_workbook.xlsx (main QA tool). No place names: ids, categories, coordinates, checks.
Run from the repository root:  python src/build_workbook.py
"""
import os

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

PROC = os.path.join("data", "processed")
OUT = os.path.join("qa", "location_qa_workbook.xlsx")
os.makedirs("qa", exist_ok=True)
HEAD = PatternFill("solid", fgColor="E1E0D9")
BOLD = Font(bold=True)
TITLE = Font(bold=True, size=14)
WRAP = Alignment(wrap_text=True, vertical="top")
FILL = {"correct": "D9EAD3", "minor_issue": "FFF2CC", "major_issue": "F4CCCC", "cannot_verify": "D9D9D9",
        "needs_adjudication": "CFE2F3"}
FOOT = "Independent case study based on public data · not affiliated with or endorsed by any AI or mapping company"

r = lambda f: pd.read_csv(os.path.join(PROC, f + ".csv"), dtype={"ban_citycode": str})
chk = r("assistant_checks")
ann = pd.read_csv(os.path.join(PROC, "annotations.csv"))
cons = r("consensus")
agr = r("agreement")
conf = r("confusion_r1_r2")

# ---------------- Final verdict = rubric v2 applied to the automatic checks (+ manual confirmation)
def rubric(row):
    c = row.auto_code
    if c == "PASS":
        return "correct", "All automatic checks passed; name still to be read against the evidence."
    if c == "NOT_FOUND":
        return "major_issue", "No record of this kind within 40 m of the BAN point in any source: likely invented (confirm by web search)."
    if c == "CLOSED_PLACE":
        return "major_issue", "Recommended place is marked closed and no active registry entry exists at the address."
    if c == "WRONG_CATEGORY":
        return "major_issue", "Place exists but is not of the requested kind (e.g. drugstore or medical supply shown as a pharmacy)."
    if c == "OUT_OF_AREA":
        return "minor_issue", "Place exists and is open but its address is outside the 11e (BAN city code is not 75111)."
    if c == "POSITION_DRIFT":
        return ("major_issue" if row.pin_vs_ban_m >= 300 else "minor_issue"), \
            "Pin is far from the BAN geocode of the shown address (150-300 m minor, >= 300 m major)."
    if c == "DUPLICATE":
        return "minor_issue", "The two listed results are the same place (records <= 40 m apart in OSM and Overture)."
    if c == "MISSING_HOURS":
        return "minor_issue", "Status answer without opening hours; status itself not contradicted (rule v2)."
    if c == "NOT_IN_REGISTRY":
        s = str(row.sources)
        if "OSM" in s and "OVERTURE" in s:
            return "correct", "Absent from the registry but confirmed by two open sources."
        return "cannot_verify", "Absent from the registry and only one open source: cannot verify from the desk."
    return "cannot_verify", ""


chk[["final_verdict", "decision_rule"]] = chk.apply(lambda x: pd.Series(rubric(x)), axis=1)
chk.to_csv(os.path.join(PROC, "audit_log.csv"), index=False)       # reused by the map, notebook and PDF
votes = ann.pivot(index="answer_id", columns="annotator_id", values="verdict")
chk = chk.merge(votes, left_on="answer_id", right_index=True).merge(cons, on="answer_id")

wb = Workbook()


def table(ws, df, start_row=1, widths=None):
    for j, col in enumerate(df.columns, 1):
        c = ws.cell(start_row, j, col); c.fill = HEAD; c.font = BOLD; c.alignment = WRAP
    for i, row in enumerate(df.itertuples(index=False), start_row + 1):
        for j, v in enumerate(row, 1):
            ws.cell(i, j, None if (isinstance(v, float) and v != v) else v)
    for j, col in enumerate(df.columns, 1):
        ws.column_dimensions[get_column_letter(j)].width = (widths or {}).get(col, max(10, min(40, len(str(col)) + 4)))
    return start_row + len(df)


# ---------------- README
ws = wb.active; ws.title = "README"
lines = [
    ("Location QA workbook: auditing local answers in Paris 11e", TITLE),
    ("PUBLIC DATA (places, registries, BAN geocodes) + SIMULATED (600 answers of a fictional assistant, 3 simulated annotators).", None),
    ("", None),
    ("How to use", BOLD),
    ("1. Read the Rubric and the Error taxonomy tabs (2 minutes).", None),
    ("2. In 'Audit log', filter one answer. Columns A-L show what the simulated assistant said. Columns M-W show the automatic checks.", None),
    ("3. Blind test: hide columns X onwards, fill 'your_verdict' (column X) for 10 answers, then unhide and compare with final_verdict.", None),
    ("4. Open the evidence links (OpenStreetMap object or map at the shown pin) to confirm by hand. Desk research only: no field visit.", None),
    ("5. 'Agreement' shows how often the 3 simulated annotators agree (Cohen's kappa) before and after guideline v2.", None),
    ("6. 'Summary' is built with formulas on the Audit log: filter or edit verdicts and it updates.", None),
    ("", None),
    ("Sources (no source is 'the truth')", BOLD),
    ("Official registries (most reliable, but lag): FINESS pharmacies (extraction 2026-05-04, Licence Ouverte); "
     "Education registry (Licence Ouverte v2.0); BAN address geocoder (Licence Ouverte).", None),
    ("Open databases (fresher, uneven): OpenStreetMap (© OpenStreetMap contributors, ODbL); Overture Maps places "
     "release 2026-11-18.0 (CDLA-Permissive-2.0 / Apache-2.0 / CC0-1.0 depending on the source record).", None),
    ("Secondary check: SIRENE establishments (activity 47.73Z), SIRET, status and position only.", None),
    ("", None),
    ("Privacy: no business or person names are stored in this workbook (many businesses carry an owner's name).", None),
    (FOOT, Font(italic=True, color="666666")),
]
for i, (t, f) in enumerate(lines, 1):
    c = ws.cell(i, 1, t)
    if f:
        c.font = f
ws.column_dimensions["A"].width = 140

# ---------------- Error taxonomy
ws = wb.create_sheet("Error taxonomy")
ex = chk.groupby("auto_code").answer_id.first()
cnt = chk.auto_code.value_counts()
tax = pd.DataFrame([
    ("CLOSED_PLACE", "Recommends a place that has closed (permanently).", "Source status closed (Overture operating_status, OSM disused:*) and no active registry entry at the address.", "major_issue"),
    ("INVENTED_PLACE", "Cites a place that exists in no source (hallucination). Automatic flag: NOT_FOUND.", "No record of the requested kind within 40 m of the BAN point of the shown address, in any of the 4 sources.", "major_issue"),
    ("WRONG_CATEGORY", "Right place, wrong kind: drugstore, medical supply shop or parapharmacy shown as a pharmacy; adult education shown as a school.", "Records found at the address, none of the requested category.", "major_issue"),
    ("POSITION_DRIFT", "Pin far from the address it displays (often bis / ter numbers).", "Distance pin vs BAN geocode of the shown address >= 150 m.", "minor < 300 m, major >= 300 m"),
    ("OUT_OF_AREA", "Place presented as in the 11e but located in a neighbouring arrondissement (border streets).", "BAN city code of the shown address is not 75111.", "minor_issue"),
    ("DUPLICATE", "The same place listed twice (OSM and Overture records under two names).", "The two cited records are <= 40 m apart.", "minor_issue"),
    ("MISSING_HOURS", "Status question answered without opening hours.", "query_type = opening_status and no hours shown.", "minor_issue"),
    ("NOT_IN_REGISTRY", "Not an error by itself: the place is absent from the official registry (which lags).", "No FINESS / Education record at the address -> look for a second source.", "correct (2 sources) or cannot_verify"),
], columns=["code", "definition", "automatic check", "severity"])
tax["example (anonymised)"] = tax.code.map(lambda c: ex.get("NOT_FOUND" if c == "INVENTED_PLACE" else c, ""))
tax["answers flagged"] = tax.code.map(lambda c: int(cnt.get("NOT_FOUND" if c == "INVENTED_PLACE" else c, 0)))
table(ws, tax, widths={"code": 18, "definition": 55, "automatic check": 60, "severity": 22, "example (anonymised)": 12})
for row in ws.iter_rows(min_row=2):
    for c in row:
        c.alignment = WRAP

# ---------------- Rubric
ws = wb.create_sheet("Rubric")
rub = pd.DataFrame([
    ("correct", "Every checked fact holds: the place exists, is open, is of the requested kind, is in the area, the pin is within 150 m of its address.", "Two independent sources agree; absence from the registry alone is not an error (rule v2)."),
    ("minor_issue", "The user still reaches a valid place, with friction: missing hours, pin 150-300 m off, duplicate result, just outside the area.", "Pick the most severe code if several apply; write the code in error_code."),
    ("major_issue", "The user is sent to the wrong place or a place that cannot serve them: closed, invented, wrong category, pin >= 300 m off.", "Major beats minor. Closed / invented need one confirming source (registry or web)."),
    ("cannot_verify", "The evidence available from the desk is not enough to decide.", "Use it when sources disagree and no second source settles it. Never guess."),
], columns=["verdict", "definition", "decision rule"])
n = table(ws, rub, widths={"verdict": 16, "definition": 80, "decision rule": 70})
for row in ws.iter_rows(min_row=2):
    for c in row:
        c.alignment = WRAP
g = r("guidelines_versions")
ws.cell(n + 2, 1, "Guideline versions").font = BOLD
table(ws, g, start_row=n + 3, widths={"version": 16, "effective_from": 80, "change": 70})
for row in ws.iter_rows(min_row=n + 4):
    for c in row:
        c.alignment = WRAP

# ---------------- Audit log
ws = wb.create_sheet("Audit log")
cols = ["answer_id", "query_type", "theme", "asked_on", "guidelines_version", "shown_address", "shown_postcode",
        "shown_lat", "shown_lon", "shown_status", "shown_category", "shown_hours",
        "ban_citycode", "pin_vs_ban_m", "records_found", "sources", "chk_not_found", "chk_closed", "chk_category",
        "chk_boundary", "chk_drift", "chk_duplicate", "auto_code",
        "your_verdict", "final_verdict", "decision_rule", "R1", "R2", "R3", "consensus_verdict", "evidence_link"]
chk["shown_address"] = chk.shown_address.fillna("")
chk["evidence_link"] = [f"https://www.openstreetmap.org/{o}" if isinstance(o, str) and o else
                        f"https://www.openstreetmap.org/?mlat={la}&mlon={lo}#map=19/{la}/{lo}"
                        for o, la, lo in zip(chk.osm_ref, chk.shown_lat, chk.shown_lon)]
chk["your_verdict"] = ""
log = chk[cols].sort_values("answer_id")
last = table(ws, log, widths={"shown_address": 30, "decision_rule": 60, "evidence_link": 45, "sources": 22})
for i in range(2, last + 1):
    c = ws.cell(i, len(cols)); c.hyperlink = c.value; c.font = Font(color="1155CC", underline="single")
ws.freeze_panes = "B2"
ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{last}"
dv = DataValidation(type="list", formula1='"correct,minor_issue,major_issue,cannot_verify"', allow_blank=True)
ws.add_data_validation(dv)
yc = get_column_letter(cols.index("your_verdict") + 1)
dv.add(f"{yc}2:{yc}{last}")
for name in ("your_verdict", "final_verdict", "R1", "R2", "R3", "consensus_verdict"):
    L = get_column_letter(cols.index(name) + 1)
    for v, color in FILL.items():
        ws.conditional_formatting.add(f"{L}2:{L}{last}", CellIsRule(operator="equal", formula=[f'"{v}"'],
                                      fill=PatternFill("solid", fgColor=color)))
for name in ("chk_not_found", "chk_closed", "chk_category", "chk_boundary", "chk_drift", "chk_duplicate"):
    L = get_column_letter(cols.index(name) + 1)
    ws.conditional_formatting.add(f"{L}2:{L}{last}", CellIsRule(operator="equal", formula=["TRUE"],
                                  fill=PatternFill("solid", fgColor="F4CCCC")))
F, Y = get_column_letter(cols.index("final_verdict") + 1), yc
ws.conditional_formatting.add(f"{Y}2:{Y}{last}", FormulaRule(formula=[f'AND({Y}2<>"",{Y}2<>{F}2)'],
                              font=Font(bold=True, color="CC0000")))

# ---------------- Agreement
ws = wb.create_sheet("Agreement")
ws.cell(1, 1, "SIMULATED - agreement between 3 simulated annotators, before (v1) and after (v2) the guideline change").font = BOLD
n = table(ws, agr, start_row=3, widths={"scope": 20, "guidelines_version": 18, "pair": 8})
ws.cell(n + 2, 1, "Confusion matrix R1 (rows) x R2 (columns)").font = BOLD
n2 = table(ws, conf, start_row=n + 3, widths={"scope": 20, "guidelines_version": 18})
ws.cell(n2 + 2, 1, "Mean kappa").font = BOLD
mk = agr.groupby(["scope", "guidelines_version"]).cohen_kappa.mean().round(3).unstack().reset_index()
n3 = table(ws, mk, start_row=n2 + 3)
ch = BarChart(); ch.type = "col"; ch.title = "Mean Cohen's kappa, v1 vs v2 (SIMULATED)"; ch.y_axis.title = "kappa"
ch.add_data(Reference(ws, min_col=2, max_col=3, min_row=n2 + 3, max_row=n3), titles_from_data=True)
ch.set_categories(Reference(ws, min_col=1, min_row=n2 + 4, max_row=n3)); ch.height, ch.width = 7, 14
ws.add_chart(ch, f"J{n2 + 2}")

# ---------------- Summary (formulas on the Audit log)
ws = wb.create_sheet("Summary")
ws.cell(1, 1, "Summary (all formulas on 'Audit log')  -  SIMULATED answers checked against PUBLIC DATA").font = TITLE
qtypes = ["find_nearest", "address_lookup", "opening_status", "category_search"]
codes = ["PASS", "NOT_FOUND", "CLOSED_PLACE", "WRONG_CATEGORY", "OUT_OF_AREA", "POSITION_DRIFT", "DUPLICATE",
         "MISSING_HOURS", "NOT_IN_REGISTRY"]
qa = f"'Audit log'!$B$2:$B${last}"; ac = f"'Audit log'!${get_column_letter(cols.index('auto_code') + 1)}$2:${get_column_letter(cols.index('auto_code') + 1)}${last}"
fv = f"'Audit log'!${F}$2:${F}${last}"
ws.cell(3, 1, "auto_code").font = BOLD
for j, q in enumerate(qtypes + ["total"], 2):
    c = ws.cell(3, j, q); c.font = BOLD; c.fill = HEAD
ws.cell(3, 1).fill = HEAD
for i, code in enumerate(codes, 4):
    ws.cell(i, 1, code)
    for j, q in enumerate(qtypes, 2):
        ws.cell(i, j, f'=COUNTIFS({ac},"{code}",{qa},"{q}")')
    ws.cell(i, len(qtypes) + 2, f"=SUM(B{i}:{get_column_letter(len(qtypes) + 1)}{i})")
tr = 4 + len(codes)
ws.cell(tr, 1, "total").font = BOLD
for j in range(2, len(qtypes) + 3):
    L = get_column_letter(j); ws.cell(tr, j, f"=SUM({L}4:{L}{tr - 1})")
ws.cell(tr + 1, 1, "% flagged (excl. PASS, NOT_IN_REGISTRY)").font = BOLD
for j in range(2, len(qtypes) + 3):
    L = get_column_letter(j)
    ws.cell(tr + 1, j, f"=1-({L}4+{L}{tr - 1})/{L}{tr}").number_format = "0.0%"
vr = tr + 4
ws.cell(vr - 1, 1, "final_verdict").font = BOLD; ws.cell(vr - 1, 1).fill = HEAD
ws.cell(vr - 1, 2, "answers").font = BOLD; ws.cell(vr - 1, 2).fill = HEAD
ws.cell(vr - 1, 3, "share").font = BOLD; ws.cell(vr - 1, 3).fill = HEAD
for i, v in enumerate(["correct", "minor_issue", "major_issue", "cannot_verify"], vr):
    ws.cell(i, 1, v); ws.cell(i, 2, f'=COUNTIF({fv},"{v}")')
    ws.cell(i, 3, f"=B{i}/SUM(B{vr}:B{vr + 3})").number_format = "0.0%"
for j in range(1, 7):
    ws.column_dimensions[get_column_letter(j)].width = 22
ch = BarChart(); ch.type = "bar"; ch.stacked = False; ch.title = "Automatic flags by code (all query types)"
ch.add_data(Reference(ws, min_col=len(qtypes) + 2, min_row=4, max_row=tr - 1))
ch.set_categories(Reference(ws, min_col=1, min_row=4, max_row=tr - 1)); ch.legend = None; ch.height, ch.width = 8, 14
ws.add_chart(ch, "H3")
ch2 = BarChart(); ch2.type = "col"; ch2.title = "Final verdicts (rubric v2)"
ch2.add_data(Reference(ws, min_col=2, min_row=vr, max_row=vr + 3))
ch2.set_categories(Reference(ws, min_col=1, min_row=vr, max_row=vr + 3)); ch2.legend = None; ch2.height, ch2.width = 7, 14
ws.add_chart(ch2, "H21")
ws.cell(vr + 6, 1, FOOT).font = Font(italic=True, color="666666")

wb.properties.creator = ""; wb.properties.lastModifiedBy = ""; wb.properties.title = ""
wb.save(OUT)
print(f"saved {OUT}: sheets={wb.sheetnames}; final verdicts={chk.final_verdict.value_counts().to_dict()}")
