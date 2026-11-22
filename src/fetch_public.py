"""Fetch the public data used by the case study (Paris 11e, INSEE 75111).

Respectful collection: at most 1 request per second, everything cached in data/raw/,
3 Overpass requests in total (3 s apart), one BAN batch upload, no key, no account.
Contact fields (phones, emails, socials, websites, fax) and owner names are dropped at ingestion.
Run from the repository root:  python src/fetch_public.py
"""
import io
import json
import os
import time

import pandas as pd
import requests

RAW = os.path.join("data", "raw")
os.makedirs(RAW, exist_ok=True)
UA = {"User-Agent": "location-qa-case-study/1.0"}
AREA = 3600009533            # OSM relation 9533 "Paris 11e Arrondissement" + 3 600 000 000
OVERTURE_RELEASE = "2026-11-18.0"
# Buffered bounding box around the 11e: also covers the border streets of the 3e, 4e, 10e, 12e, 20e
BBOX = dict(xmin=2.352, xmax=2.412, ymin=48.843, ymax=48.876)
FINESS_URL = ("https://static.data.gouv.fr/resources/finess-extraction-du-fichier-des-etablissements/"
              "20260512-091152/etalab-cs1100507-stock-20260512-0339.csv")
EDU_URL = ("https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-annuaire-education/records"
           "?where=code_commune%3D%2275111%22&limit=100")
SIRENE_URL = "https://recherche-entreprises.api.gouv.fr/near_point"
BAN_CSV_URL = "https://api-adresse.data.gouv.fr/search/csv/"

_last = [0.0]


def polite_get(url, **kw):
    """GET with a 1 request/second ceiling."""
    wait = 1.0 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    r = requests.get(url, headers=UA, timeout=kw.pop("timeout", 120), **kw)
    _last[0] = time.time()
    return r


def cached(name):
    return os.path.exists(os.path.join(RAW, name))


# ---------------------------------------------------------------- OpenStreetMap (Overpass)
OVERPASS = "https://overpass-api.de/api/interpreter"
QUERIES = {
    "osm_pharmacies.json": f"""[out:json][timeout:90];
area({AREA})->.a;
(nwr["amenity"="pharmacy"](area.a);nwr["healthcare"="pharmacy"](area.a);
 nwr["disused:amenity"="pharmacy"](area.a);nwr["shop"="chemist"](area.a);
 nwr["shop"="medical_supply"](area.a););
out center tags;""",
    "osm_schools.json": f"""[out:json][timeout:90];
area({AREA})->.a;
(nwr["amenity"="school"](area.a);nwr["amenity"="kindergarten"](area.a);
 nwr["amenity"="college"](area.a);nwr["disused:amenity"="school"](area.a););
out center tags;""",
    "osm_boundary.json": """[out:json][timeout:90];
rel(9533);out geom;""",
}


def fetch_overpass():
    first = True
    for name, q in QUERIES.items():
        if cached(name):
            continue
        if not first:
            time.sleep(3)
        first = False
        for attempt in (1, 2):
            r = requests.post(OVERPASS, data={"data": q}, headers=UA, timeout=180)
            try:
                js = r.json()
                break
            except ValueError:
                js = None
                if attempt == 1:          # 429 or non-JSON answer: wait 30 s, retry once only
                    print(f"  Overpass {name}: HTTP {r.status_code}, non-JSON, retry in 30 s")
                    time.sleep(30)
        if js is None:
            print(f"  Overpass failed twice for {name}: skipped (no loop). Re-run the script later.")
            return
        with open(os.path.join(RAW, name), "w", encoding="utf-8") as f:
            json.dump(js, f)
        print(f"  {name}: {len(js.get('elements', []))} elements")


# ---------------------------------------------------------------- Overture Maps places
def fetch_overture():
    out = os.path.join(RAW, "overture_places.parquet")
    if os.path.exists(out):
        return
    import duckdb
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    src = f"s3://overturemaps-us-west-2/release/{OVERTURE_RELEASE}/theme=places/type=place/*"
    # phones, emails, socials and websites are never selected
    con.execute(f"""
        COPY (
          SELECT id,
                 (bbox.xmin + bbox.xmax) / 2 AS lon,
                 (bbox.ymin + bbox.ymax) / 2 AS lat,
                 confidence, operating_status, basic_category,
                 to_json(taxonomy)  AS taxonomy_json,
                 names."primary"    AS name,
                 to_json(addresses) AS addresses_json,
                 to_json(brand)     AS brand_json,
                 to_json(sources)   AS sources_json,
                 version
          FROM read_parquet('{src}', hive_partitioning = 1)
          WHERE bbox.xmin BETWEEN {BBOX['xmin']} AND {BBOX['xmax']}
            AND bbox.ymin BETWEEN {BBOX['ymin']} AND {BBOX['ymax']}
        ) TO '{out.replace(os.sep, '/')}' (FORMAT parquet)""")
    n = con.execute(f"SELECT count(*) FROM '{out.replace(os.sep, '/')}'").fetchone()[0]
    print(f"  overture_places.parquet: {n} places")


# ---------------------------------------------------------------- FINESS (official health registry)
def fetch_finess():
    raw = os.path.join(RAW, "finess_stock.csv")
    if not os.path.exists(raw):
        r = polite_get(FINESS_URL, timeout=600)
        r.raise_for_status()
        with open(raw, "wb") as f:
            f.write(r.content)
    out = os.path.join(RAW, "finess_paris_pharmacies.csv")
    if os.path.exists(out):
        return
    struct, geo = [], {}
    with open(raw, encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").split(";")
            if p[0] == "structureet" and len(p) > 30 and p[13] == "75":
                struct.append(p)
            elif p[0] == "geolocalisation" and len(p) >= 4:
                geo[p[1]] = (p[2], p[3])
    rows = []
    for p in struct:
        if p[18] != "620":            # 620 = pharmacie d'officine
            continue
        x, y = geo.get(p[1], ("", ""))
        # telephone (16) and telecopie (17) are dropped here
        rows.append(dict(finess=p[1], name=p[3], numvoie=p[7], typvoie=p[8], voie=p[9], compvoie=p[10],
                         postcode=p[15][:5], categ=p[18], categ_label=p[19], siret=p[22],
                         date_open=p[28], date_maj=p[30], x_l93=x, y_l93=y))
    df = pd.DataFrame(rows)
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)
    xs = pd.to_numeric(df.x_l93, errors="coerce")
    ys = pd.to_numeric(df.y_l93, errors="coerce")
    lon, lat = t.transform(xs.values, ys.values)
    df["lon"], df["lat"] = lon, lat
    df.drop(columns=["x_l93", "y_l93"]).to_csv(out, index=False)
    print(f"  FINESS: {len(df)} pharmacies in Paris, {int((df.postcode == '75011').sum())} in 75011")


# ---------------------------------------------------------------- Education registry
EDU_KEEP = ["identifiant_de_l_etablissement", "nom_etablissement", "type_etablissement", "statut_public_prive",
            "adresse_1", "code_postal", "latitude", "longitude", "etat", "date_ouverture", "ecole_maternelle",
            "ecole_elementaire"]


def fetch_education():
    out = os.path.join(RAW, "education_75111.csv")
    if os.path.exists(out):
        return
    js = polite_get(EDU_URL).json()
    df = pd.DataFrame(js["results"])
    df = df[[c for c in EDU_KEEP if c in df.columns]]       # telephone, mail, web dropped
    df.to_csv(out, index=False)
    print(f"  Education registry: {len(df)} records (total_count={js.get('total_count')})")


# ---------------------------------------------------------------- SIRENE (secondary check)
def fetch_sirene():
    out = os.path.join(RAW, "sirene_4773Z.csv")
    if os.path.exists(out):
        return
    rows, page = [], 1
    while page <= 10:
        js = polite_get(SIRENE_URL, params=dict(lat=48.8590, long=2.3790, radius=1.6,
                                                 activite_principale="47.73Z", per_page=25, page=page)).json()
        for res in js.get("results", []):
            for e in res.get("matching_etablissements", []):
                # nom_complet / dirigeants are never kept (pharmacists often trade under their own name)
                rows.append(dict(siret=e.get("siret"), activite=e.get("activite_principale"),
                                 address=e.get("adresse"), etat=e.get("etat_administratif"),
                                 lat=e.get("latitude"), lon=e.get("longitude"),
                                 date_creation=e.get("date_creation"), date_fermeture=e.get("date_fermeture")))
        if page >= js.get("total_pages", 1):
            break
        page += 1
    pd.DataFrame(rows).drop_duplicates("siret").to_csv(out, index=False)
    print(f"  SIRENE 47.73Z: {len(rows)} establishments ({page} pages)")


# ---------------------------------------------------------------- Licence pages (one request each)
def fetch_licences():
    out = os.path.join(RAW, "licences.json")
    if os.path.exists(out):
        return
    lic = {}
    try:
        js = polite_get("https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-annuaire-education").json()
        lic["education"] = js.get("metas", {}).get("default", {}).get("license")
    except Exception as e:                         # metadata endpoint did not answer JSON at test time
        lic["education"] = f"not retrieved ({type(e).__name__})"
    try:
        html = polite_get("https://docs.overturemaps.org/attribution/").text
        lic["overture_places_snippet"] = " ".join(
            s for s in html.split("<") if "lace" in s and ("CDLA" in s or "ODbL" in s or "Apache" in s))[:2000]
    except Exception as e:
        lic["overture_places_snippet"] = f"not retrieved ({type(e).__name__})"
    json.dump(lic, open(out, "w", encoding="utf-8"), indent=1)


# ---------------------------------------------------------------- Normalisation + BAN batch geocoding
import math
import unicodedata

import numpy as np

PROC = os.path.join("data", "processed")
TYPVOIE = {"R": "Rue", "BD": "Boulevard", "AV": "Avenue", "PL": "Place", "PAS": "Passage", "IMP": "Impasse",
           "CHE": "Chemin", "QU": "Quai", "QUA": "Quai", "SQ": "Square", "CR": "Cour", "ALL": "Allee",
           "CITE": "Cite", "CI": "Cite", "VLA": "Villa", "VOIE": "Voie", "RPT": "Rond-point", "SEN": "Sentier"}
COMPVOIE = {"B": "bis", "T": "ter", "Q": "quater"}
NAME_NOISE = ["pharmacie", "pharmacy", "grande", "de la", "du", "des", "de", "le", "la", "les", "l'", "d'",
              "ecole", "elementaire", "maternelle", "primaire", "college", "lycee", "publique", "privee", "polyvalente"]


def norm_name(s):
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    for ch in "-'.,()/":
        s = s.replace(ch, " ")
    words = [w for w in s.split() if w not in NAME_NOISE]
    return " ".join(words)


def boundary_rings():
    js = json.load(open(os.path.join(RAW, "osm_boundary.json"), encoding="utf-8"))
    ways = [[(p["lon"], p["lat"]) for p in m["geometry"]]
            for m in js["elements"][0]["members"] if m["type"] == "way" and m.get("role") == "outer"]
    rings = []
    while ways:
        ring = ways.pop(0)
        while ring[0] != ring[-1] and ways:
            for i, w in enumerate(ways):
                if w[0] == ring[-1]:
                    ring += w[1:]; ways.pop(i); break
                if w[-1] == ring[-1]:
                    ring += w[::-1][1:]; ways.pop(i); break
            else:
                break
        rings.append(ring)
    return rings


def in_poly(lon, lat, rings):
    inside = False
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                inside = not inside
    return inside


def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371000 * 2 * np.arcsin(np.sqrt(a))


def osm_rows(fname, theme):
    rows = []
    for e in json.load(open(os.path.join(RAW, fname), encoding="utf-8"))["elements"]:
        t = e.get("tags", {})
        lat = e.get("lat", e.get("center", {}).get("lat"))
        lon = e.get("lon", e.get("center", {}).get("lon"))
        status = "open"
        if theme == "pharmacy":
            if t.get("amenity") == "pharmacy" or t.get("healthcare") == "pharmacy":
                cat = "parapharmacy" if t.get("dispensing") == "no" else "pharmacy"
            elif t.get("disused:amenity") == "pharmacy":
                cat, status = "pharmacy", "closed"
            elif t.get("shop") == "chemist":
                cat = "drugstore"
            else:
                cat = "medical_supply"
            raw = "|".join(f"{k}={t[k]}" for k in ("amenity", "healthcare", "shop", "dispensing", "disused:amenity") if k in t)
        else:
            a = t.get("amenity", "")
            if t.get("disused:amenity") == "school":
                cat, status = "school", "closed"
            elif a == "kindergarten":
                cat = "kindergarten_or_nursery"
            elif a == "college":
                cat = "higher_or_adult_education"
            else:
                cat = "school"
            raw = "|".join(f"{k}={t[k]}" for k in ("amenity", "isced:level", "school:FR", "disused:amenity") if k in t)
        hn, st = t.get("addr:housenumber", ""), t.get("addr:street", "")
        rows.append(dict(theme=theme, source="OSM", source_id=f"{e['type']}/{e['id']}", name=t.get("name"),
                         category=cat, raw_category=raw, status=status, lat=lat, lon=lon,
                         address=f"{hn} {st}".strip() if hn and st else "", postcode=t.get("addr:postcode", ""),
                         has_opening_hours=int("opening_hours" in t), confidence=None))
    return rows


def prepare():
    os.makedirs(PROC, exist_ok=True)
    rings = boundary_rings()
    gj = {"type": "Feature", "properties": {"name": "Paris 11e (OSM relation 9533)", "licence": "ODbL"},
          "geometry": {"type": "MultiPolygon", "coordinates": [[[list(p) for p in r]] for r in rings]}}
    json.dump(gj, open(os.path.join(PROC, "boundary_11e.geojson"), "w"))
    rows = osm_rows("osm_pharmacies.json", "pharmacy") + osm_rows("osm_schools.json", "school")
    # FINESS (official registry): every listed pharmacy is considered active at extraction date
    fi = pd.read_csv(os.path.join(RAW, "finess_paris_pharmacies.csv"), dtype=str)
    for r in fi.itertuples():
        num = r.numvoie if isinstance(r.numvoie, str) else ""
        comp = COMPVOIE.get(r.compvoie, "") if isinstance(r.compvoie, str) else ""
        typ = TYPVOIE.get(r.typvoie, r.typvoie if isinstance(r.typvoie, str) else "")
        addr = " ".join(x for x in (num, comp, typ, r.voie if isinstance(r.voie, str) else "") if x)
        rows.append(dict(theme="pharmacy", source="FINESS", source_id=r.finess, name=r.name, category="pharmacy",
                         raw_category=f"categetab={r.categ}", status="open", lat=float(r.lat), lon=float(r.lon),
                         address=addr.title(), postcode=r.postcode, has_opening_hours=None, confidence=None,
                         date_open=r.date_open))
    ed = pd.read_csv(os.path.join(RAW, "education_75111.csv"), dtype=str)
    for r in ed.itertuples():
        typ = r.type_etablissement
        cat = ("school" if typ == "Ecole" else "secondary_school" if typ in ("Collège", "Lycée")
               else "other_education")
        st = "open" if str(r.etat).upper().startswith("OUVERT") else "closed" if "FERM" in str(r.etat).upper() else "other"
        rows.append(dict(theme="school", source="EDU", source_id=r.identifiant_de_l_etablissement,
                         name=r.nom_etablissement, category=cat, raw_category=f"{typ}|{r.statut_public_prive}",
                         status=st, lat=float(r.latitude), lon=float(r.longitude), address=r.adresse_1,
                         postcode=r.code_postal, has_opening_hours=None, confidence=None, date_open=r.date_ouverture))
    import duckdb
    ov = duckdb.connect().execute(f"""
        SELECT id, name, lon, lat, confidence, operating_status, basic_category,
               json_extract_string(taxonomy_json, '$.primary') AS tax,
               json_extract_string(addresses_json, '$[0].freeform') AS addr,
               json_extract_string(addresses_json, '$[0].postcode') AS pc,
               json_extract_string(sources_json, '$[0].license') AS lic
        FROM '{RAW}/overture_places.parquet'""".replace("\\", "/")).df()
    ov_school = {"elementary_school", "preschool", "middle_school", "high_school"}
    for r in ov.itertuples():
        if r.basic_category == "pharmacy_and_drug_store":
            theme, cat = "pharmacy", ("pharmacy" if r.tax == "pharmacy" else "drugstore")
        elif r.basic_category in ov_school:
            theme = "school"
            cat = ("school" if r.basic_category in ("elementary_school", "preschool") else "secondary_school")
        else:
            continue
        st = {"open": "open", "permanently_closed": "closed", "temporarily_closed": "temporarily_closed"}.get(
            r.operating_status, "unknown")
        rows.append(dict(theme=theme, source="OVERTURE", source_id=r.id, name=r.name, category=cat,
                         raw_category=f"{r.basic_category}|{r.tax}", status=st, lat=r.lat, lon=r.lon,
                         address=r.addr or "", postcode=r.pc or "", has_opening_hours=None,
                         confidence=round(float(r.confidence), 3) if r.confidence == r.confidence else None,
                         licence=r.lic))
    df = pd.DataFrame(rows)
    df = df[df.lon.between(BBOX["xmin"], BBOX["xmax"]) & df.lat.between(BBOX["ymin"], BBOX["ymax"])].copy()
    df["in_11e"] = [int(in_poly(lo, la, rings)) for lo, la in zip(df.lon, df.lat)]
    df["name_norm"] = df.name.map(norm_name)
    df["bis_ter"] = df.address.str.contains(r"\b(?:bis|ter|quater)\b|\d+\s?[BT]\b", case=False, regex=True).astype(int)
    df = df.sort_values(["theme", "source", "source_id"]).reset_index(drop=True)
    df.insert(0, "place_id", [f"P{i:04d}" for i in range(1, len(df) + 1)])

    # Background pool of real addresses (other Overture places in the 11e) used for "invented place" answers
    pool = ov[~ov.basic_category.isin(["pharmacy_and_drug_store"] + list(ov_school)) & ov.addr.notna()
              & (ov.pc == "75011")].sample(250, random_state=42)
    pool = pd.DataFrame({"place_id": [f"Q{i:04d}" for i in range(1, len(pool) + 1)],
                         "address": pool.addr.values, "postcode": "75011"})

    # One single BAN batch upload for every address
    ban_cache = os.path.join(RAW, "ban_results.csv")
    q = pd.concat([df.loc[df.address != "", ["place_id", "address", "postcode"]], pool])
    q["postcode"] = q.postcode.fillna("").astype(str).str[:5]
    q["address"] = q.address + " Paris"          # without it, addresses lacking a postcode match other towns
    if not os.path.exists(ban_cache):
        buf = io.StringIO(); q.to_csv(buf, index=False)
        time.sleep(1)
        r = requests.post(BAN_CSV_URL, headers=UA, timeout=300,
                          files={"data": ("addresses.csv", buf.getvalue().encode("utf-8"), "text/csv")},
                          data={"columns": "address", "postcode": "postcode"})
        r.raise_for_status()
        open(ban_cache, "wb").write(r.content)
    ban = pd.read_csv(ban_cache, dtype={"place_id": str, "result_citycode": str})
    ban = ban.rename(columns={"latitude": "ban_lat", "longitude": "ban_lon"})
    keep = ["place_id", "ban_lat", "ban_lon", "result_score", "result_type", "result_citycode", "result_label"]
    ban = ban[[c for c in keep if c in ban.columns]].rename(columns={
        "result_score": "ban_score", "result_type": "ban_type", "result_citycode": "ban_citycode",
        "result_label": "ban_label"})
    ban.loc[~ban.ban_citycode.astype(str).str.startswith("751"), ["ban_lat", "ban_lon"]] = np.nan  # outside Paris
    df = df.merge(ban, on="place_id", how="left")
    df["ban_dist_m"] = haversine(df.lat, df.lon, df.ban_lat, df.ban_lon).round(1)
    df.to_csv(os.path.join(RAW, "norm_places.csv"), index=False)              # with names: never published
    pool.merge(ban, on="place_id").to_csv(os.path.join(RAW, "norm_address_pool.csv"), index=False)
    pub = df.drop(columns=["name", "name_norm", "address", "ban_label"])        # published: no names
    pub.to_csv(os.path.join(PROC, "places.csv"), index=False)
    print(f"  places: {len(df)} rows; in 11e: {int(df.in_11e.sum())}; geocoded: {int(df.ban_lat.notna().sum())}")
    print(df[df.in_11e == 1].groupby(["theme", "source", "category"]).size().to_string())


if __name__ == "__main__":
    print("Overpass"); fetch_overpass()
    print("Overture"); fetch_overture()
    print("FINESS"); fetch_finess()
    print("Education"); fetch_education()
    print("SIRENE"); fetch_sirene()
    print("Licences"); fetch_licences()
    print("Normalise + BAN"); prepare()
