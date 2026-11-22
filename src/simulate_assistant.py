"""SIMULATED data: 600 answers of a fictional local-search assistant + 3 simulated annotators (seed 42).

No LLM is called. Answers are built from the real public places (data/raw/norm_places.csv, made by
fetch_public.py) with planted errors. The answer key goes to data/_hidden_truth.csv (never published)
and is only opened after the automatic checks have run.
Run from the repository root:  python src/simulate_assistant.py
"""
import os
import re

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
RAW, PROC = os.path.join("data", "raw"), os.path.join("data", "processed")
os.makedirs(PROC, exist_ok=True)
V2_DATE = pd.Timestamp("2026-11-12")


def hav(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371000 * 2 * np.arcsin(np.sqrt(a))


def shift(lat, lon, metres, bearing):
    dlat = metres * np.cos(bearing) / 111_320
    dlon = metres * np.sin(bearing) / (111_320 * np.cos(np.radians(lat)))
    return lat + dlat, lon + dlon


def street(label):
    return re.sub(r"\s\d{5}\s.*$", "", str(label)).strip()


P = pd.read_csv(os.path.join(RAW, "norm_places.csv"), dtype={"ban_citycode": str, "source_id": str})
pool = pd.read_csv(os.path.join(RAW, "norm_address_pool.csv"), dtype={"ban_citycode": str}).dropna(subset=["ban_lat"])
P = P[P.ban_lat.notna() | P.source.isin(["OSM"])].copy()
P["street"] = P.ban_label.map(lambda x: street(x) if isinstance(x, str) else "")
geo = P[P.ban_lat.notna()]

# Published BAN geocodes, keyed by street label (what a reviewer would type in the BAN search)
ban_pub = pd.concat([
    geo[["street", "ban_citycode", "ban_lat", "ban_lon", "ban_score", "ban_type"]],
    pool.assign(street=pool.ban_label.map(street))[["street", "ban_citycode", "ban_lat", "ban_lon", "ban_score", "ban_type"]],
]).drop_duplicates("street")
ban_pub = ban_pub[ban_pub.street != ""]
ban_pub.to_csv(os.path.join(PROC, "ban_geocodes.csv"), index=False)

ph = P[P.theme == "pharmacy"]
fin = ph[ph.source == "FINESS"]


def nearest_dist(sub, ref):
    if len(ref) == 0:
        return np.full(len(sub), np.inf)
    d = hav(sub.lat.values[:, None], sub.lon.values[:, None], ref.lat.values[None, :], ref.lon.values[None, :])
    return d.min(axis=1)


# ---- pools of places
reg_ph = fin[(fin.in_11e == 1)]
reg_sc = P[(P.source == "EDU") & (P.in_11e == 1) & (P.category == "school") & (P.status == "open")]
closed = ph[(ph.in_11e == 1) & (ph.status == "closed") & (ph.street != "")]
closed = closed[nearest_dist(closed, fin) > 30]            # not contradicted by an active registry entry nearby
bis = P[(P.in_11e == 1) & (P.bis_ter == 1) & (P.ban_dist_m < 30) & (P.street != "")]   # pin agrees with BAN
wrongcat = P[(P.in_11e == 1) & P.category.isin(["drugstore", "medical_supply", "parapharmacy",
                                                 "higher_or_adult_education"]) & (P.street != "")]
outside = fin[(fin.in_11e == 0) & (fin.street != "")]
outside = outside[nearest_dist(outside, P[(P.in_11e == 1)]) < 450]   # just across a border street
osm_ph = ph[(ph.source == "OSM") & (ph.in_11e == 1) & (ph.category == "pharmacy") & (ph.status == "open")]
ov_ph = ph[(ph.source == "OVERTURE") & (ph.in_11e == 1) & (ph.category == "pharmacy") & (ph.status == "open")]
open_data = pd.concat([osm_ph, ov_ph])
lag = open_data[(nearest_dist(open_data, fin) > 50) & (open_data.street != "")].copy()
lag["second_source"] = [
    (nearest_dist(r.to_frame().T.astype({"lat": float, "lon": float}),
                  (ov_ph if r.source == "OSM" else osm_ph)) <= 50)[0] for _, r in lag.iterrows()]
# duplicate pairs: OSM and Overture records of the same pharmacy (<= 40 m)
d = hav(osm_ph.lat.values[:, None], osm_ph.lon.values[:, None], ov_ph.lat.values[None, :], ov_ph.lon.values[None, :])
pairs = [(osm_ph.iloc[i].place_id, ov_ph.iloc[j].place_id) for i, j in zip(*np.where(d <= 40))
         if ov_ph.iloc[j].street != ""]
print(f"pools: reg_ph={len(reg_ph)} reg_sc={len(reg_sc)} closed={len(closed)} bis={len(bis)} "
      f"wrongcat={len(wrongcat)} outside={len(outside)} lag={len(lag)} pairs={len(pairs)}")

# ---- plan: (event, query_type)
PLAN = ([(1, "find_nearest")] * 20 + [(1, "opening_status")] * 16 +
        [(2, "find_nearest")] * 10 + [(2, "category_search")] * 8 +
        [(3, "address_lookup")] * 24 +
        [(4, "category_search")] * 14 + [(4, "find_nearest")] * 10 +
        [(5, "category_search")] * 14 + [(5, "find_nearest")] * 10 +
        [(6, "category_search")] * 18 +
        [(7, "find_nearest")] * 10 + [(7, "opening_status")] * 8 +
        [(8, "opening_status")] * 40)
TARGET = {"find_nearest": 190, "address_lookup": 150, "opening_status": 140, "category_search": 120}
for qt, n in TARGET.items():
    PLAN += [(0, qt)] * (n - sum(1 for _, q in PLAN if q == qt))
order = rng.permutation(len(PLAN))
PLAN = [PLAN[i] for i in order]

days = pd.date_range("2026-11-02", "2026-11-20", freq="D")
dates = np.sort(rng.choice(days, size=len(PLAN)))

TRUTH = {0: ("correct", ""), 1: ("major_issue", "CLOSED_PLACE"), 2: ("major_issue", "INVENTED_PLACE"),
         4: ("major_issue", "WRONG_CATEGORY"), 5: ("minor_issue", "OUT_OF_AREA"), 6: ("minor_issue", "DUPLICATE"),
         8: ("minor_issue", "MISSING_HOURS")}
SHOWN_CAT = {"pharmacy": "pharmacy", "school": "school"}

answers, truth = [], []
for k, ((ev, qt), day) in enumerate(zip(PLAN, dates), start=1):
    aid = f"A{k:04d}"
    theme = "pharmacy"
    if qt == "address_lookup" and ev == 0 and rng.random() < 0.6:
        theme = "school"
    if qt == "find_nearest" and ev == 0 and rng.random() < 0.35:
        theme = "school"
    ref2, hours = "", ""
    if ev == 0:
        base = reg_sc if theme == "school" else reg_ph
        if qt == "find_nearest":                      # query point first, then the true nearest registry place
            anchor = base.sample(1, random_state=int(rng.integers(1e9))).iloc[0]
            qlat, qlon = shift(anchor.lat, anchor.lon, rng.uniform(80, 400), rng.uniform(0, 2 * np.pi))
            row = base.iloc[int(np.argmin(hav(qlat, qlon, base.lat.values, base.lon.values)))]
        else:
            row = base.sample(1, random_state=int(rng.integers(1e9))).iloc[0]
        if qt == "opening_status":
            hours = "yes"
    else:
        src = {1: closed, 3: bis, 4: wrongcat, 5: outside, 7: lag, 8: reg_ph}.get(ev)
        if ev == 4 and qt == "find_nearest":
            src = wrongcat[wrongcat.category == "higher_or_adult_education"]
            theme = "school"
        if ev == 4 and qt == "category_search":
            src = wrongcat[wrongcat.category != "higher_or_adult_education"]
        if ev == 3:
            theme = rng.choice(["pharmacy", "school"]) if (bis.theme == "school").any() else "pharmacy"
            src = bis[bis.theme == theme] if (bis.theme == theme).any() else bis
            theme = src.theme.iloc[0] if not (src.theme == theme).all() else theme
        if ev == 2:
            row = pool.sample(1, random_state=int(rng.integers(1e9))).iloc[0]
            row = row.copy(); row["street"] = street(row.ban_label)
        elif ev == 6:
            a, b = pairs[int(rng.integers(len(pairs)))]
            row = P.set_index("place_id").loc[b].copy(); row["place_id"] = b   # Overture record (has an address)
            ref2 = a
        else:
            row = src.sample(1, random_state=int(rng.integers(1e9))).iloc[0]
        if qt == "opening_status":
            hours = "no" if ev == 8 else "yes"
    lat0 = row.ban_lat if (isinstance(row.get("ban_lat"), float) and row.ban_lat == row.ban_lat) else row.lat
    lon0 = row.ban_lon if (isinstance(row.get("ban_lon"), float) and row.ban_lon == row.ban_lon) else row.lon
    if ev in (0, 1, 4, 5, 6, 7, 8) and "lat" in row and row.lat == row.lat:
        lat0, lon0 = row.lat, row.lon
    if ev == 3:
        drift = rng.uniform(160, 420)
        slat, slon = shift(lat0, lon0, drift, rng.uniform(0, 2 * np.pi))
    else:
        slat, slon = shift(lat0, lon0, rng.uniform(0, 6), rng.uniform(0, 2 * np.pi))
    if not (ev == 0 and qt == "find_nearest"):
        qlat, qlon = shift(lat0, lon0, rng.uniform(80, 450), rng.uniform(0, 2 * np.pi))
    shown_status = {"opening_status": "open now", "find_nearest": "open", "category_search": "open",
                    "address_lookup": ""}[qt]
    answers.append(dict(
        answer_id=aid, query_type=qt, theme=theme, asked_on=pd.Timestamp(day).date().isoformat(),
        query_lat=round(qlat, 6), query_lon=round(qlon, 6),
        place_ref=("NONE" if ev == 2 else row.place_id), place_ref_2=ref2,
        shown_address=row.street if row.street else "", shown_postcode="75011",
        shown_lat=round(slat, 6), shown_lon=round(slon, 6), shown_status=shown_status,
        shown_category=SHOWN_CAT[theme], shown_hours=hours))
    if ev == 3:
        verdict, code = ("major_issue" if drift >= 300 else "minor_issue"), "POSITION_DRIFT"
    elif ev == 7:
        verdict, code = ("correct", "NOT_IN_REGISTRY") if row.second_source else ("cannot_verify", "NOT_IN_REGISTRY")
    else:
        verdict, code = TRUTH[ev]
    truth.append(dict(answer_id=aid, event_id=ev, true_verdict=verdict, true_code=code))

A = pd.DataFrame(answers)
T = pd.DataFrame(truth)
A["guidelines_version"] = np.where(pd.to_datetime(A.asked_on) >= V2_DATE, "v2", "v1")

# ---- 3 simulated annotators
VERDICTS = ["correct", "minor_issue", "major_issue", "cannot_verify"]
ACC = {"R1": 0.93, "R2": 0.90, "R3": 0.91}


def neighbour(v):
    return {"correct": rng.choice(["minor_issue", "cannot_verify"], p=[.7, .3]),
            "minor_issue": rng.choice(["correct", "major_issue"]),
            "major_issue": rng.choice(["minor_issue", "cannot_verify"], p=[.8, .2]),
            "cannot_verify": rng.choice(["correct", "minor_issue"])}[v]


ann = []
for a, t in zip(A.itertuples(), T.itertuples()):
    for r in ("R1", "R2", "R3"):
        v = t.true_verdict
        if a.guidelines_version == "v1" and t.true_code == "MISSING_HOURS":     # event 8: rule unclear in v1
            v = {"R1": rng.choice(["minor_issue", "major_issue"], p=[.9, .1]),
                 "R2": rng.choice(["major_issue", "minor_issue"], p=[.9, .1]),
                 "R3": rng.choice(["minor_issue", "major_issue"])}[r]
        elif a.guidelines_version == "v1" and t.true_code == "NOT_IN_REGISTRY":  # v1: "not in registry" unclear
            v = {"R1": "correct", "R2": "major_issue", "R3": "cannot_verify"}[r]
            if rng.random() > 0.85:
                v = neighbour(v)
        elif a.guidelines_version == "v1" and t.true_code == "POSITION_DRIFT":   # v1: no distance threshold
            v = rng.choice(["minor_issue", "major_issue"])
        elif rng.random() > ACC[r] + (0.03 if a.guidelines_version == "v2" else 0):
            v = neighbour(v)
        code = "" if v in ("correct", "cannot_verify") else (t.true_code if t.true_code else "OTHER")
        if code == "NOT_IN_REGISTRY" and v in ("minor_issue", "major_issue"):
            code = "INVENTED_PLACE"                     # what an annotator believes when the registry is silent
        secs = rng.lognormal(np.log(78), 0.42)
        if v == "cannot_verify" or t.true_code in ("INVENTED_PLACE", "NOT_IN_REGISTRY"):
            secs *= 1.45
        if a.guidelines_version == "v2":
            secs *= 0.85
        ann.append(dict(annotator_id=r, answer_id=a.answer_id, guidelines_version=a.guidelines_version,
                        verdict=v, error_code=code, seconds=int(round(secs))))
N = pd.DataFrame(ann)

G = pd.DataFrame([
    dict(version="v1", effective_from="2026-11-02", change="Initial rubric: correct / minor / major / cannot_verify; "
         "no rule for missing opening hours, places absent from the registry, or position thresholds."),
    dict(version="v2", effective_from=V2_DATE.date().isoformat(), change="Added: (1) missing hours when the status is "
         "otherwise right = minor_issue; (2) absent from the official registry is not proof of error: confirm in a "
         "second independent source (correct) or answer cannot_verify; (3) pin vs BAN geocode: <150 m ok, "
         "150-300 m minor_issue, >=300 m major_issue."),
])

A.to_csv(os.path.join(PROC, "assistant_answers.csv"), index=False)
N.to_csv(os.path.join(PROC, "annotations.csv"), index=False)
G.to_csv(os.path.join(PROC, "guidelines_versions.csv"), index=False)
T9 = pd.concat([T, pd.DataFrame([dict(answer_id="", event_id=9, true_verdict="",
                true_code="FALSE_SIGNAL: Overture 'has many more pharmacies' (bbox + broad category); not a defect")])])
T9.to_csv(os.path.join("data", "_hidden_truth.csv"), index=False)
print(f"answers={len(A)} annotations={len(N)} issues={int((T.true_verdict != 'correct').sum())} "
      f"median_seconds={int(N.seconds.median())}")
print(T.groupby(["event_id", "true_verdict"]).size().to_string())
