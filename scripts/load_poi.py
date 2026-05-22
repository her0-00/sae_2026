"""
Chargement des gares + écoles via Overpass API — direct vers PostgreSQL.
Lance : python scripts/load_poi.py
Durée : ~20 min
"""
import logging, sys, time, urllib.parse
from pathlib import Path
import psycopg2.extras
import requests
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.config import DEPARTEMENTS, BBOXES
from scripts._db import get_conn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("poi")

OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]


def overpass_query(query: str) -> list:
    payload = urllib.parse.urlencode({"data": query})
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    for base in OVERPASS:
        try:
            r = requests.post(base, data=payload, headers=headers, timeout=120)
            if r.status_code == 200:
                return r.json().get("elements", [])
            log.warning("  HTTP %d sur %s", r.status_code, base.split("/")[2])
        except Exception as e:
            log.warning("  %s : %s", base.split("/")[2], e)
        time.sleep(2)
    return []


def inserer(elements: list, type_poi: str, conn) -> int:
    batch = []
    for el in elements:
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lng = el.get("lon") or (el.get("center") or {}).get("lon")
        if not lat or not lng:
            continue
        nom = (el.get("tags") or {}).get("name", "")
        batch.append((type_poi, nom, float(lat), float(lng)))
    if not batch:
        return 0
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO points_interet (type,nom,latitude,longitude,geom) VALUES %s ON CONFLICT DO NOTHING",
            [(t, n, lat, lng, f"SRID=4326;POINT({lng} {lat})") for t, n, lat, lng in batch],
        )
    conn.commit()
    return len(batch)


def charger_poi(dept: str, conn):
    bbox_t = BBOXES.get(dept.zfill(2))
    if not bbox_t:
        log.warning("[%s] Pas de bbox — skippé", dept)
        return 0, 0
    bbox = f"{bbox_t[0]},{bbox_t[1]},{bbox_t[2]},{bbox_t[3]}"

    els_g = overpass_query(f"""
        [out:json][timeout:90];
        (node["railway"="station"]({bbox});node["railway"="halt"]({bbox}););
        out body;
    """)
    n_g = inserer(els_g, "gare", conn)
    log.info("[%s] ✓ %d gares", dept, n_g)
    time.sleep(1)

    els_e = overpass_query(f"""
        [out:json][timeout:90];
        (node["amenity"="school"]({bbox});way["amenity"="school"]({bbox}););
        out center;
    """)
    n_e = inserer(els_e, "ecole", conn)
    log.info("[%s] ✓ %d écoles", dept, n_e)
    return n_g, n_e


def main():
    log.info("POI — %d départements", len(DEPARTEMENTS))
    conn = get_conn()
    tot_g = tot_e = 0
    for dept in DEPARTEMENTS:
        try:
            g, e = charger_poi(dept, conn)
            tot_g += g
            tot_e += e
        except Exception as ex:
            log.error("[%s] %s", dept, ex)
    conn.close()
    log.info("TOTAL %d gares | %d écoles", tot_g, tot_e)


if __name__ == "__main__":
    main()
