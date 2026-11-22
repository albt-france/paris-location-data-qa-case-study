"""Build report/Location_QA_audit_Paris11.pdf (6 pages): HTML + inline SVG charts -> Edge headless -> pypdf
(metadata emptied). The intermediate HTML goes to data/raw/report_build/ (not published).
Run from the repository root:  python src/build_pdf.py
"""
import io
import json
import os
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from pypdf import PdfReader, PdfWriter

PROC = os.path.join("data", "processed")
BUILD = os.path.join("data", "raw", "report_build")
OUT = os.path.join("report", "Location_QA_audit_Paris11.pdf")
os.makedirs(BUILD, exist_ok=True); os.makedirs("report", exist_ok=True)
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
plt.rcParams.update({"font.family": "Segoe UI", "font.size": 9, "svg.fonttype": "none", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#999999", "axes.labelcolor": "#444444",
                     "xtick.color": "#444444", "ytick.color": "#444444", "axes.titlesize": 9.5})
C = {"FINESS": "#1f4e79", "EDU": "#1f4e79", "OSM": "#7e57c2", "OVERTURE": "#00897b", "grey": "#b0aca3",
     "correct": "#2e7d32", "minor_issue": "#f9a825", "major_issue": "#c62828", "cannot_verify": "#8a8a8a",
     "v1": "#c9c4b8", "v2": "#1f4e79"}
r = lambda f: pd.read_csv(os.path.join(PROC, f + ".csv"))


def svg(fig):
    buf = io.StringIO(); fig.savefig(buf, format="svg", bbox_inches="tight", transparent=True); plt.close(fig)
    s = buf.getvalue()
    return s[s.find("<svg"):]


def bar_labels(ax, bars, fmt="{:.0f}", dx=0.5):
    for b in bars:
        w = b.get_width()
        ax.text(w + dx, b.get_y() + b.get_height() / 2, fmt.format(w), va="center", fontsize=8, color="#333333")


# ------------------------------------------------------------------ data
fs = r("false_signal"); ms = r("matching_summary"); audit = r("audit_log"); agr = r("agreement")
conf = r("confusion_r1_r2"); nir = r("not_in_registry"); db = r("drift_bands"); xd = r("cross_source_duplicates")
reg = r("registry_missing_in_open"); tpt = r("time_per_task"); ann = r("annotations")
codes = audit.auto_code.value_counts()
flagged = int((~audit.auto_code.isin(["PASS", "NOT_IN_REGISTRY"])).sum())
verdicts = audit.final_verdict.value_counts()
k = agr.groupby(["scope", "guidelines_version"]).cohen_kappa.mean().round(2)
med = ann.groupby("guidelines_version").seconds.median()
fin_osm = ms.query("theme=='pharmacy' and source=='FINESS' and other_source=='OSM'").iloc[0]
fin_ov = ms.query("theme=='pharmacy' and source=='FINESS' and other_source=='OVERTURE'").iloc[0]

# ------------------------------------------------------------------ charts
charts = {}
# false signal
fig, ax = plt.subplots(figsize=(4.6, 2.05))
lab = ["1. First count\n(download box, 'pharm')", "2. Same area\n(11e polygon)", "3. Same category\n(taxonomy = pharmacy)",
       "4. Same status\n(open only)"]
bars = ax.barh(lab[::-1], fs.overture[::-1], color=[C["OVERTURE"]] * 3 + [C["grey"]], height=0.6)
bars[-1].set_color(C["grey"])
for b in bars[:-1]:
    b.set_color(C["OVERTURE"])
bar_labels(ax, bars, dx=4)
ax.axvline(fs.osm[0], color=C["OSM"], ls="--", lw=1.2); ax.axvline(fs.finess[0], color=C["FINESS"], ls=":", lw=1.4)
ax.text(fs.osm[0] - 3, 3.55, f"OSM {fs.osm[0]}", color=C["OSM"], fontsize=8, ha="right")
ax.text(fs.finess[0] + 3, 3.55, f"FINESS {fs.finess[0]}", color=C["FINESS"], fontsize=8)
ax.set_xlabel("Overture pharmacy records"); ax.set_xlim(0, 340); ax.set_ylim(-0.5, 3.9)
charts["false_signal"] = svg(fig)

# match rates
fig, ax = plt.subplots(figsize=(4.6, 2.5))
m = ms.copy(); m["pair"] = m.source + " → " + m.other_source
m = m[m.source.isin(["FINESS", "EDU", "OSM"])]
m = m[~((m.source == "OSM") & (m.theme == "school"))]
colors = [C[o] for o in m.other_source]
bars = ax.barh([f"{t}: {p}" for t, p in zip(m.theme, m.pair)][::-1], m.pct_matched[::-1], color=colors[::-1], height=0.6)
bar_labels(ax, bars, "{:.0f}%", dx=1)
ax.set_xlim(0, 112); ax.set_xlabel("% of records found in the other source (11e)")
charts["match"] = svg(fig)

# codes
fig, ax = plt.subplots(figsize=(4.6, 2.6))
order = ["CLOSED_PLACE", "MISSING_HOURS", "WRONG_CATEGORY", "OUT_OF_AREA", "POSITION_DRIFT", "DUPLICATE", "NOT_FOUND",
         "NOT_IN_REGISTRY"]
sev = {"CLOSED_PLACE": "major_issue", "NOT_FOUND": "major_issue", "WRONG_CATEGORY": "major_issue",
       "POSITION_DRIFT": "minor_issue", "OUT_OF_AREA": "minor_issue", "DUPLICATE": "minor_issue",
       "MISSING_HOURS": "minor_issue", "NOT_IN_REGISTRY": "cannot_verify"}
vals = [100 * codes.get(c, 0) / 600 for c in order]
bars = ax.barh([c.replace("_", " ").lower() + (" (invented)" if c == "NOT_FOUND" else "") for c in order][::-1],
               vals[::-1], color=[C[sev[c]] for c in order][::-1], height=0.6)
bar_labels(ax, bars, "{:.1f}%", dx=0.1)
ax.set_xlabel("% of the 600 answers (automatic code)"); ax.set_xlim(0, 8.5)
charts["codes"] = svg(fig)

# by query type
er = r("error_rates").sort_values("pct_flagged")
fig, ax = plt.subplots(figsize=(4.6, 1.9))
bars = ax.barh(er.query_type.str.replace("_", " "), er.pct_flagged, color=C["major_issue"], height=0.55, alpha=0.85)
bar_labels(ax, bars, "{:.0f}%", dx=0.6); ax.set_xlim(0, 55); ax.set_xlabel("% of answers flagged")
charts["qtype"] = svg(fig)

# answers map (no tiles, no labels)
gj = json.load(open(os.path.join(PROC, "boundary_11e.geojson")))
fig, ax = plt.subplots(figsize=(3.9, 3.6))
for poly in gj["geometry"]["coordinates"]:
    xs, ys = zip(*poly[0]); ax.plot(xs, ys, color="#333333", lw=1, ls="--")
for v in ["correct", "cannot_verify", "minor_issue", "major_issue"]:
    s = audit[audit.final_verdict == v]
    ax.scatter(s.shown_lon, s.shown_lat, s=7 if v == "correct" else 11, color=C[v], label=f"{v.replace('_', ' ')} ({len(s)})",
               alpha=0.8, lw=0)
ax.set_aspect(1 / 0.657); ax.axis("off")
ax.legend(loc="lower left", fontsize=7, frameon=False, bbox_to_anchor=(-0.02, -0.12), ncol=2)
charts["map"] = svg(fig)

# not in registry
fig, ax = plt.subplots(figsize=(4.4, 1.9))
a = nir.assessment.value_counts()
lab_order = ["probable pin offset of a registry pharmacy", "cannot verify (desk research only)",
             "confirmed by a second source", "likely stale: ceased SIRENE establishment nearby"]
colors = [C["grey"], C["cannot_verify"], C["correct"], C["major_issue"]]
bars = ax.barh([l.split(":")[0].replace(" of a registry pharmacy", "").replace(" (desk research only)", "")
                for l in lab_order][::-1], [a.get(l, 0) for l in lab_order][::-1], color=colors[::-1], height=0.55)
bar_labels(ax, bars, dx=0.1); ax.set_xlabel(f"open-data pharmacies with no FINESS match (n = {len(nir)})")
ax.set_xlim(0, 8)
charts["nir"] = svg(fig)

# drift bands
fig, ax = plt.subplots(figsize=(4.6, 1.9))
p = db[db.source.isin(["OSM", "OVERTURE"])].pivot(index="band", columns="source", values="n").fillna(0)
pct = p / p.sum() * 100
x = range(len(pct)); w = 0.38
for i, s in enumerate(["OSM", "OVERTURE"]):
    bb = ax.bar([xi + (i - 0.5) * w for xi in x], pct[s], w, color=C[s], label=f"{'OSM' if s == 'OSM' else 'Overture'} (n = {int(p[s].sum())})")
ax.set_xticks(list(x)); ax.set_xticklabels([b.split(": ")[1] for b in pct.index])
ax.set_ylabel("% of geocoded records"); ax.legend(frameon=False, fontsize=7.5)
charts["drift"] = svg(fig)

# duplicates distance histogram
fig, ax = plt.subplots(figsize=(4.6, 1.7))
ax.hist(xd.dist_m, bins=range(0, 32, 2), color=C["OVERTURE"], alpha=0.85, edgecolor="white")
ax.set_xlabel("distance between the OSM and Overture records (m)"); ax.set_ylabel("pairs")
charts["dups"] = svg(fig)

# kappa by pair
fig, ax = plt.subplots(figsize=(4.6, 1.95))
sub = agr[agr.scope == "all answers"]
pairs = sub.pair.unique(); w = 0.36
for i, v in enumerate(["v1", "v2"]):
    vals = [sub[(sub.pair == pp) & (sub.guidelines_version == v)].cohen_kappa.iloc[0] for pp in pairs]
    bb = ax.bar([j + (i - 0.5) * w for j in range(len(pairs))], vals, w, color=C[v], label=f"guidelines {v}")
    for b in bb:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.015, f"{b.get_height():.2f}", ha="center", fontsize=7.5)
sub2 = agr[agr.scope == "opening_status only"]
ax.set_xticks(range(len(pairs))); ax.set_xticklabels(pairs); ax.set_ylim(0, 1.22); ax.set_yticks([0, .2, .4, .6, .8, 1]); ax.set_ylabel("Cohen's kappa")
ax.legend(frameon=False, fontsize=7.5, loc="upper left", ncol=2)
charts["kappa"] = svg(fig)

fig, ax = plt.subplots(figsize=(4.6, 1.6))
vals = [k[("opening_status only", "v1")], k[("opening_status only", "v2")], k[("all answers", "v1")], k[("all answers", "v2")]]
bars = ax.barh(["opening status, v1", "opening status, v2", "all answers, v1", "all answers, v2"][::-1], vals[::-1],
               color=[C["v2"], C["v1"], C["v2"], C["v1"]], height=0.55)
bar_labels(ax, bars, "{:.2f}", dx=0.01); ax.set_xlim(0, 1); ax.set_xlabel("mean Cohen's kappa (3 pairs)")
charts["kappa_scope"] = svg(fig)

# confusion matrices
fig, axes = plt.subplots(1, 2, figsize=(4.8, 2.2))
labels = ["correct", "minor", "major", "cannot"]
for ax, v in zip(axes, ["v1", "v2"]):
    mtx = conf[conf.guidelines_version == v][["r2_correct", "r2_minor_issue", "r2_major_issue", "r2_cannot_verify"]].values
    ax.imshow(mtx, cmap="Greys", vmin=0, vmax=mtx.max() * 1.6)
    for i in range(mtx.shape[0]):
        for j in range(mtx.shape[1]):
            ax.text(j, i, int(mtx[i, j]), ha="center", va="center", fontsize=7.5,
                    color="#c62828" if i != j and mtx[i, j] >= 8 else "#222222")
    ax.set_xticks(range(4)); ax.set_xticklabels(labels, fontsize=7, rotation=30); ax.set_yticks(range(4))
    ax.set_yticklabels(labels if v == "v1" else [], fontsize=7); ax.set_title(f"guidelines {v}", fontsize=8.5)
    ax.set_xlabel("R2 verdict", fontsize=7.5)
    for s in ax.spines.values():
        s.set_visible(False)
axes[0].set_ylabel("R1 verdict", fontsize=7.5)
charts["confusion"] = svg(fig)

# ------------------------------------------------------------------ HTML
FOOT = "Independent case study based on public data · not affiliated with or endorsed by any AI or mapping company"
AI = ("AI-assisted workflow: I used Claude, mainly to write scripts faster. I drove the project: I defined the "
      "questions, chose and validated the data sources, made the analytical decisions and checked every result.")
CSS = """
@page { size: 297mm 210mm; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: 'Segoe UI', sans-serif; color: #222; background: #ebe8e1; }
.page { width: 297mm; height: 210mm; padding: 9mm 11mm 7mm; background: #ebe8e1; page-break-after: always;
        display: flex; flex-direction: column; overflow: hidden; }
.page:last-child { page-break-after: auto; }
.kicker { font-size: 9pt; color: #6b665c; letter-spacing: .04em; text-transform: uppercase; }
h1 { font-size: 19pt; margin: 1mm 0 1mm; font-weight: 600; line-height: 1.15; }
h2 { font-size: 10.5pt; margin: 0 0 1.5mm; font-weight: 600; padding-right: 21mm; }
.sub { font-size: 9.5pt; color: #4a463e; margin-bottom: 3mm; }
.grid { display: grid; gap: 4mm; flex: 1; min-height: 0; }
.card { background: #fff; border-radius: 3mm; padding: 3.5mm 4mm; box-shadow: 0 .3mm 1mm rgba(0,0,0,.07);
        overflow: hidden; position: relative; }
.card svg { width: 100%; height: auto; max-height: 100%; }
.tag { position: absolute; top: 3mm; right: 3.5mm; font-size: 6.5pt; font-weight: 700; letter-spacing: .05em;
       padding: .6mm 1.6mm; border-radius: 1mm; }
.pub { background: #dde8f3; color: #1f4e79; } .sim { background: #fbe5c8; color: #8a4b00; }
.note { font-size: 8pt; color: #555; margin-top: 1mm; line-height: 1.35; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4mm; margin-bottom: 4mm; }
.kpi { background: #fff; border-radius: 3mm; padding: 3mm 4mm; position: relative; }
.kpi b { display: block; font-size: 20pt; font-weight: 600; color: #1f4e79; }
.kpi span { font-size: 8.3pt; color: #444; }
ul, ol { margin: 0; padding-left: 4.5mm; font-size: 8.8pt; line-height: 1.42; }
li { margin-bottom: .8mm; }
table { border-collapse: collapse; width: 100%; font-size: 8pt; }
td, th { border-bottom: .2mm solid #e3e0d8; padding: .9mm 1.2mm; text-align: left; vertical-align: top; }
th { color: #6b665c; font-weight: 600; }
.foot { display: flex; justify-content: space-between; font-size: 7pt; color: #7a756b; margin-top: 2.5mm; }
p { font-size: 8.8pt; line-height: 1.42; margin: 0 0 1.5mm; }
"""


def page(n, kicker, title, sub, body):
    return f"""<section class="page"><div class="kicker">{kicker}</div><h1>{title}</h1><div class="sub">{sub}</div>
{body}<div class="foot"><span>{FOOT}</span><span>Paris 11e location QA · {n + 1} / 6</span></div></section>"""


def card(title, content, tag="pub", note=""):
    t = '<span class="tag pub">PUBLIC DATA</span>' if tag == "pub" else '<span class="tag sim">SIMULATED</span>' \
        if tag == "sim" else ""
    return f'<div class="card">{t}<h2>{title}</h2>{content}{f"<div class=note>{note}</div>" if note else ""}</div>'


nir_counts = nir.assessment.value_counts()
both = int((reg.in_osm & reg.in_overture).sum()); neither = int((~reg.in_osm & ~reg.in_overture).sum())
pages = []

pages.append(page(0, "Overview · map & location QA case study",
    "Can you trust the map? Auditing AI-generated local answers in one Paris district",
    "Paris 11e · pharmacies, schools, addresses · official registries vs open databases · 600 answers of a simulated assistant",
    f"""<div class="kpis">
<div class="kpi"><span class="tag sim">SIMULATED</span><b>{100 * flagged / 600:.0f}%</b><span>of the 600 simulated answers carry an issue ({verdicts.get('major_issue', 0)} major, {verdicts.get('minor_issue', 0)} minor); {verdicts.get('cannot_verify', 0)} cannot be verified from the desk</span></div>
<div class="kpi"><span class="tag sim">SIMULATED</span><b>182 / 184</b><span>planted issues caught by 8 automatic checks; the 2 misses are invented places only a name check reveals</span></div>
<div class="kpi"><span class="tag sim">SIMULATED</span><b>{k[('all answers', 'v1')]:.2f} → {k[('all answers', 'v2')]:.2f}</b><span>annotator agreement (Cohen's kappa) after 3 clearer rules; {med['v1']:.0f} s → {med['v2']:.0f} s per task</span></div>
<div class="kpi"><span class="tag pub">PUBLIC DATA</span><b>{fin_osm.pct_matched:.0f}% / {fin_ov.pct_matched:.0f}%</b><span>of the {int(fin_osm.records)} registry pharmacies found in OpenStreetMap / Overture; the "5x more pharmacies" gap was a counting artefact</span></div>
</div>
<div class="grid" style="grid-template-columns: 1fr 1.25fr 1fr;">
{card("Five questions", '''<ol><li>Do the official registries and the open databases agree on what is in the district?</li>
<li>What goes wrong in AI-generated local answers, and how often?</li><li>Which errors can be caught automatically, and which need a human?</li>
<li>When the registry is silent, is the place invented or is the registry late?</li><li>Do two reviewers give the same verdict, and what makes them agree?</li></ol>''', tag="")}
{card("Recommendations", '''<ol><li><b>Geocode first.</b> A BAN house-number lookup settles position (150 / 300 m thresholds) and area (city code) in seconds.</li>
<li><b>Never call a place invented from one source.</b> Absent from the registry → second source, else <i>cannot verify</i>. Most registry gaps here were pin offsets.</li>
<li><b>Compare like with like</b> before raising a source issue: same area, same category, same status.</li>
<li><b>Write rules for the grey zones</b> (missing hours, registry gaps, distance): they drive disagreement, not the obvious errors.</li>
<li><b>Keep a human on the name</b>: an invented place at a real address passes every automatic check.</li></ol>''', tag="")}
{card("Method", f'''<ul><li><b>Real part:</b> FINESS (pharmacies), Education registry (schools), BAN (addresses) vs OpenStreetMap and Overture, inside the OSM boundary of the 11e.</li>
<li><b>Simulated part:</b> 600 answers of a fictional assistant built from the real places with planted errors; 3 simulated annotators, guidelines v1 then v2.</li>
<li><b>Workflow:</b> error taxonomy → 8 automatic checks (SQL, DuckDB) → manual review → rubric → agreement (kappa) → guideline fix.</li>
<li><b>Deliverables:</b> QA workbook, interactive map, guidelines, checklist, notebook.</li><li>Desk research only; no place names published.</li></ul>''', tag="")}
</div>"""))

pages.append(page(1, "1 · Four sources, one district",
    "Like for like, the open databases agree with the registry: the '5x more pharmacies' gap was a counting artefact",
    f"First count: 300 Overture 'pharm' records vs {fs.osm[0]} OSM pharmacies. Same polygon, same category, same status: {fs.overture[3]} vs {fs.osm[0]} (OSM) and {fs.finess[0]} (FINESS).",
    f"""<div class="grid" style="grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr;">
{card("False signal, recounted step by step (pharmacies)", charts["false_signal"], note="Not reported as a data defect. The download box was wider than the district and the category filter caught drugstores and closed places.")}
{card("Match rate between sources (distance + name)", charts["match"], note="Match rule: same theme and ≤ 30 m, or ≤ 120 m with name similarity ≥ 0.85. Schools match less: one building often holds several registry entries.")}
{card("What each source holds in the 11e", f'''<table><tr><th>Source</th><th>Type</th><th>Pharmacies</th><th>Schools</th><th>Status field</th></tr>
<tr><td>FINESS</td><td>registry, extract 2026-05-04</td><td>59</td><td>–</td><td>listed = active</td></tr>
<tr><td>Education registry</td><td>registry</td><td>–</td><td>84 (+12 other)</td><td>etat: all open</td></tr>
<tr><td>OpenStreetMap</td><td>open, community</td><td>56 open (+2 closed, 4 other shops)</td><td>60 (+66 nurseries / higher ed.)</td><td>disused:*</td></tr>
<tr><td>Overture 2026-11-18.0</td><td>open, aggregated</td><td>81 (60 open, 4 closed, 17 unknown) + 3 drugstores</td><td>56 (54 status unknown)</td><td>operating_status</td></tr></table>''', note="Counts inside the OSM boundary of the 11e (relation 9533).")}
{card("Registry pharmacies found in the open sources", f'''<p style="font-size:10pt"><b>{both}</b> of 59 in both OSM and Overture · <b>{int((reg.in_osm & ~reg.in_overture).sum())}</b> in OSM only · <b>{int((~reg.in_osm & reg.in_overture).sum())}</b> in Overture only · <b>{neither}</b> in neither.</p>
<p>Median distance between matched records: {fin_osm.median_dist_m:.1f} m (FINESS–OSM), {fin_ov.median_dist_m:.1f} m (FINESS–Overture).</p>
<p><b>Reading:</b> for pharmacies both open databases are close to the registry once compared on the same basis. Overture adds value through <i>operating_status</i> and <i>confidence</i>, but its broad category (<i>pharmacy_and_drug_store</i>) must be narrowed with <i>taxonomy</i>.</p>''')}
</div>"""))

pages.append(page(2, "2 · What goes wrong in local answers",
    f"3 in 10 simulated answers had an issue: closed places and missing hours lead, invented places are the hardest to catch",
    "600 answers of a SIMULATED assistant (no real model called), checked against PUBLIC DATA. Code = first failing automatic check.",
    f"""<div class="grid" style="grid-template-columns: 1.05fr 1.05fr 0.9fr; grid-template-rows: 1fr 0.85fr;">
<div style="grid-row: span 2; display:grid; gap:4mm; grid-template-rows: 1.15fr 0.85fr;">
{card("Issues by type (share of 600 answers)", charts["codes"], tag="sim", note="Red = major, amber = minor, grey = needs a second source. 'Not in registry' is not an error by itself.")}
{card("Flag rate by question type", charts["qtype"], tag="sim", note="List questions (category search) and status questions fail most; address lookups least.")}
</div>
<div style="grid-row: span 2">{card("Where the answers point (pin shown by the assistant)", charts["map"], tag="sim", note="Dashed line: OSM boundary of the 11e. Amber dots outside it: answers presented as 11e but across a border street. No base map, no place names.")}</div>
{card("How the checks work", '''<ul><li><b>Exists:</b> record of the requested kind within 40 m of the BAN point, in any source.</li>
<li><b>Open:</b> source status closed and no active registry entry.</li><li><b>Kind:</b> category at the address.</li>
<li><b>Area:</b> BAN city code = 75111.</li><li><b>Position:</b> pin vs BAN ≥ 150 m.</li><li><b>Duplicate, hours:</b> answer fields.</li></ul>''', tag="")}
{card("Caught vs missed (answer key opened after the checks)", '''<p><b>182 of 184</b> planted issues got the right code; <b>0</b> false alarms on 398 clean answers.</p>
<p>Missed: 2 invented places. One sits at an address that really hosts a pharmacy, so every automatic check passes. Only reading the name against the evidence catches it.</p>
<p class="note">Optimistic: errors and checks were designed together.</p>''', tag="sim")}
</div>"""))

pages.append(page(3, "3 · Registries lag, open data drifts",
    "'Not in the registry' rarely meant 'invented': most gaps were pins placed 60-100 m off a known pharmacy",
    f"FINESS is an extraction of 2026-05-04. SIRENE shows no pharmacy created or closed in the 11e since then, so the lag created no false 'invented' flag here; the rule still matters.",
    f"""<div class="grid" style="grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr;">
{card(f"{len(nir)} open-data pharmacies with no FINESS match", charts["nir"], note=f"{nir_counts.get('probable pin offset of a registry pharmacy', 0)} pins 63-102 m from a registry pharmacy; {nir_counts.get('confirmed by a second source', 0)} confirmed by another source or an active SIRENE establishment ≤ 50 m; 1 stale record (ceased SIRENE establishment 27 m away); {nir_counts.get('cannot verify (desk research only)', 0)} left as cannot verify.")}
{card("Pin vs BAN geocode of the record's own address", charts["drift"], note="Registries (FINESS, Education) sit on the BAN point (median 0 m). OSM: median 6.5 m, 90th percentile 40 m (only 41 of 188 objects carry a full address). Overture: median 2.9 m, 9 pins ≥ 150 m.")}
{card(f"Same pharmacy, two names: {len(xd)} OSM–Overture pairs", charts["dups"], note=f"Records ≤ 30 m apart (median {xd.dist_m.median():.1f} m) whose names differ (Jaro-Winkler < 0.85): a merge on names would add {len(xd)} phantom pharmacies. Match on distance first, then name.")}
{card("What this means for a reviewer", '''<ul><li><b>Registry = reference, not truth.</b> It is the most reliable source for existence, but it lags (6 months here).</li>
<li><b>Open data = fresher, uneven.</b> Good coverage of pharmacies; status unknown for most Overture schools; a few pins far off.</li>
<li><b>Bis / ter addresses:</b> no real record drifts ≥ 150 m, but simulated answers with bis / ter pins 160-420 m off were the typical position error.</li>
<li><b>Schema change:</b> Overture dropped <i>categories.primary</i>; queries must be checked at every release.</li></ul>''', tag="")}
</div>"""))

pages.append(page(4, "4 · Same answer, different verdicts",
    f"Three clearer rules lifted annotator agreement from kappa {k[('all answers', 'v1')]:.2f} to {k[('all answers', 'v2')]:.2f}, and cut task time",
    "3 SIMULATED annotators rate all 600 answers; guidelines v1 until 2026-11-11, v2 from 2026-11-12. Kappa corrects raw agreement for chance.",
    f"""<div class="grid" style="grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr;">
{card("Cohen's kappa per pair of annotators", charts["kappa"], tag="sim", note="0.41-0.60 moderate, 0.61-0.80 substantial, > 0.80 almost perfect (Landis & Koch).")}
{card("R1 vs R2: where they disagreed", charts["confusion"], tag="sim", note="v1: R2 rates missing hours as major, R1 as minor; 'not in registry' split three ways. v2 empties the off-diagonal cells.")}
{card("Opening-status questions drove the disagreement", charts["kappa_scope"], tag="sim", note=f"Median time per task: {med['v1']:.0f} s with v1, {med['v2']:.0f} s with v2 (checklist in 6 steps, under 2 minutes).")}
{card("What changed in the guidelines (v1 → v2)", '''<table><tr><th>Grey zone</th><th>v1</th><th>v2 rule</th></tr>
<tr><td>Missing opening hours</td><td>not covered: minor or major by taste</td><td>minor, unless the status itself is wrong</td></tr>
<tr><td>Absent from the registry</td><td>read as "invented" by some</td><td>second source → correct; none → cannot verify</td></tr>
<tr><td>Pin far from the address</td><td>no threshold</td><td>&lt; 150 m ok · 150-300 m minor · ≥ 300 m major</td></tr></table>
<p class="note">The obvious errors (closed, invented, wrong kind) were rated consistently under both versions. Disagreement lived in the grey zones, so that is where the guideline work paid off.</p>''', tag="")}
</div>"""))

pages.append(page(5, "5 · Methods, limits & AI note",
    "Public data, simulated answers, reproducible in 8 commands",
    "All sources read on 2026-11-22 · area: Paris 11e (OSM relation 9533, INSEE 75111) · desk research only, no field visit",
    f"""<div class="grid" style="grid-template-columns: 1.45fr 1fr 1fr;">
{card("Sources, dates, licences", '''<table><tr><th>Source</th><th>Version / date</th><th>Licence</th></tr>
<tr><td>FINESS establishments (Ministry of Health)</td><td>extraction 2026-05-04</td><td>Licence Ouverte</td></tr>
<tr><td>Education registry (annuaire de l'éducation)</td><td>read 2026-11-22</td><td>Licence Ouverte v2.0</td></tr>
<tr><td>BAN address API (batch CSV)</td><td>read 2026-11-22</td><td>Licence Ouverte</td></tr>
<tr><td>OpenStreetMap via Overpass</td><td>read 2026-11-22</td><td>ODbL · © OpenStreetMap contributors</td></tr>
<tr><td>Overture Maps places</td><td>release 2026-11-18.0</td><td>per record: CDLA-Permissive-2.0, Apache-2.0, CC0-1.0 (as stated on docs.overturemaps.org/attribution, checked 2026-11-22)</td></tr>
<tr><td>SIRENE (recherche-entreprises API)</td><td>read 2026-11-22</td><td>Licence Ouverte</td></tr></table>
<p class="note">Collection: ≤ 1 request per second, cached; 3 Overpass queries; 1 BAN batch upload; Overture read in place with DuckDB. Contact fields and owner names dropped at ingestion.</p>''', tag="pub")}
{card("Method & assumptions", '''<ul><li>Python (pandas, DuckDB SQL 01-07, openpyxl, folium, matplotlib); one executed notebook.</li>
<li>Places are kept inside the OSM boundary of the 11e; border places are kept for the area check.</li>
<li>Matching: ≤ 30 m, or ≤ 120 m with name similarity ≥ 0.85 (Jaro-Winkler).</li>
<li>Evidence radius around the BAN point: 40 m; second-source radius: 50 m.</li>
<li>600 answers, 3 annotators, seed 42; 9 hidden events (8 issues, 1 false signal) kept in an answer key opened after the checks.</li>
<li>No place or person names in any published file: ids P0001…, categories, coordinates, check flags.</li></ul>''', tag="")}
{card("Limits & AI note", f'''<ul><li><b>Desk research only:</b> no field visit; "open" means open in a source.</li>
<li><b>The assistant is simulated:</b> no real model was called and no answer is attributed to any product. Real error mixes will differ.</li>
<li>Recall of the checks (182/184) is optimistic: errors and checks were designed together.</li>
<li>Annotators are simulated; kappa values illustrate the method, not real people.</li>
<li>FINESS lags 6 months; SIRENE read on 10 result pages; one district, two themes.</li></ul>
<p style="margin-top:2.5mm"><b>{AI}</b></p>''', tag="")}
</div>"""))

html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Location QA audit, Paris 11e</title>
<style>{CSS}</style></head><body>{''.join(pages)}</body></html>"""
src = os.path.abspath(os.path.join(BUILD, "report.html"))
open(src, "w", encoding="utf-8").write(html)
tmp = os.path.abspath(os.path.join(BUILD, "report_raw.pdf"))
subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
                f"--print-to-pdf={tmp}", "file:///" + src.replace("\\", "/")], check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
rd = PdfReader(tmp); wr = PdfWriter()
for pg in rd.pages:
    wr.add_page(pg)
wr.add_metadata({"/Producer": "", "/Creator": "", "/Title": "", "/Author": ""})
with open(OUT, "wb") as f:
    wr.write(f)
print(f"saved {OUT}: {len(rd.pages)} pages")
