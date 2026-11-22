"""Build map/index.html (folium, self-contained). Tooltips: id, category, failed check. No place names.
Base map without labels (Esri World Light Gray Base) so that no business name is displayed.
Run from the repository root:  python src/build_map.py
"""
import json
import os

import folium
import pandas as pd

PROC = os.path.join("data", "processed")
os.makedirs("map", exist_ok=True)
places = pd.read_csv(os.path.join(PROC, "places.csv"), dtype={"source_id": str})
places = places[(places.in_11e == 1) & places.category.isin(
    ["pharmacy", "school", "secondary_school", "drugstore", "medical_supply", "parapharmacy"])]
audit = pd.read_csv(os.path.join(PROC, "audit_log.csv"))
VCOL = {"correct": "#2e7d32", "minor_issue": "#f9a825", "major_issue": "#c62828", "cannot_verify": "#757575"}
SCOL = {"FINESS": "#1f4e79", "EDU": "#1f4e79", "OSM": "#7e57c2", "OVERTURE": "#00897b"}

m = folium.Map(location=[48.8590, 2.3800], zoom_start=15, tiles=None, control_scale=True)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    attr='Base map: Powered by Esri (Esri, HERE, Garmin, &copy; OpenStreetMap contributors) | Places: OpenStreetMap (ODbL), Overture Maps '
         'Foundation (CDLA-Permissive-2.0 / Apache-2.0 / CC0-1.0 by source), FINESS, Education registry and BAN '
         '(Licence Ouverte)',
    name="Base map (no labels)", max_zoom=19, max_native_zoom=16).add_to(m)

gj = json.load(open(os.path.join(PROC, "boundary_11e.geojson")))
folium.GeoJson(gj, name="Paris 11e boundary (OSM relation 9533)",
               style_function=lambda f: {"color": "#333333", "weight": 2, "fill": False, "dashArray": "6 4"}).add_to(m)

for label, srcs in [("Official registries (FINESS, Education) - PUBLIC DATA", ["FINESS", "EDU"]),
                    ("OpenStreetMap - PUBLIC DATA", ["OSM"]), ("Overture Maps - PUBLIC DATA", ["OVERTURE"])]:
    fg = folium.FeatureGroup(name=label, show=(srcs[0] == "FINESS"))
    for p in places[places.source.isin(srcs)].itertuples():
        tip = (f"{p.place_id} · {p.source} · {p.theme}/{p.category} · status: {p.status}"
               + (f" · pin vs BAN: {p.ban_dist_m:.0f} m" if p.ban_dist_m == p.ban_dist_m else ""))
        folium.CircleMarker([p.lat, p.lon], radius=4 if srcs[0] != "FINESS" else 5, weight=1,
                            color=SCOL[p.source], fill=True, fill_opacity=0.75 if p.status != "closed" else 0.15,
                            tooltip=tip).add_to(fg)
    fg.add_to(m)

fg = folium.FeatureGroup(name="Simulated assistant answers, colour = final verdict - SIMULATED", show=True)
for a in audit.itertuples():
    tip = (f"{a.answer_id} · SIMULATED · {a.query_type} · {a.theme} · check: {a.auto_code} · "
           f"verdict: {a.final_verdict}")
    folium.CircleMarker([a.shown_lat, a.shown_lon], radius=3.5, weight=1.2, color=VCOL[a.final_verdict],
                        fill=True, fill_opacity=0.9, tooltip=tip).add_to(fg)
fg.add_to(m)
folium.LayerControl(collapsed=False).add_to(m)

legend = """<div style="position:fixed;bottom:18px;left:12px;z-index:9999;background:#fff;padding:8px 10px;
border-radius:8px;font:12px 'Segoe UI',sans-serif;box-shadow:0 1px 4px rgba(0,0,0,.25);max-width:330px">
<b>Can you trust the map? Paris 11e</b><br>
<span style="color:#2e7d32">&#9679;</span> correct &nbsp;<span style="color:#f9a825">&#9679;</span> minor issue &nbsp;
<span style="color:#c62828">&#9679;</span> major issue &nbsp;<span style="color:#757575">&#9679;</span> cannot verify<br>
Answers are SIMULATED; places are PUBLIC DATA. No place names are shown.<br>
<span style="color:#666">Independent case study based on public data · not affiliated with or endorsed by any AI or
mapping company</span></div>"""
m.get_root().html.add_child(folium.Element(legend))
m.get_root().header.add_child(folium.Element("<title>Location QA map - Paris 11e</title>"))
m.save(os.path.join("map", "index.html"))
print("saved map/index.html", len(places), "places,", len(audit), "answers")
