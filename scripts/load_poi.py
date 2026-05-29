"""
Chargement des gares (API SNCF officielle) + écoles (Overpass OSM).
Lance : python scripts/load_poi.py

Gares  : API SNCF data.sncf.com — téléchargement national unique, filtre par bbox
Écoles : Overpass API (OpenStreetMap) — requête par département
"""
import logging, sys, time, urllib.parse
from pathlib import Path
import psycopg2.extras
import requests
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts import config
from scripts.config import BBOXES
from scripts._db import get_conn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("poi")

SNCF_URL = "https://data.sncf.com/api/explore/v2.1/catalog/datasets/gares-de-voyageurs/exports/json?limit=-1"

OVERPASS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]
HEADERS_OVP = {
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Mozilla/5.0 (compatible; SAE2026/1.0)",
}


# ── Gares SNCF ───────────────────────────────────────────────────────────────

def charger_toutes_gares_sncf() -> list:
    """Télécharge le référentiel national des gares SNCF (une fois pour tous les depts)."""
    log.info("Téléchargement référentiel gares SNCF …")
    try:
        r = requests.get(SNCF_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
        gares = r.json()
        log.info("  %d gares SNCF chargées (national)", len(gares))
        return gares
    except Exception as e:
        log.error("  Impossible de charger les gares SNCF : %s", e)
        return []


def filtrer_gares_bbox(gares: list, bbox: tuple) -> list:
    """Filtre les gares qui se trouvent dans la bounding box du département."""
    lat_min, lon_min, lat_max, lon_max = bbox
    result = []
    for g in gares:
        pos = g.get("position_geographique") or {}
        lat = pos.get("lat")
        lng = pos.get("lon")
        if lat is None or lng is None:
            continue
        if lat_min <= lat <= lat_max and lon_min <= lng <= lon_max:
            result.append({
                "nom":         g.get("nom", ""),
                "latitude":    lat,
                "longitude":   lng,
                "commune_code": str(g.get("codeinsee") or "").zfill(5) or None,
            })
    return result


def inserer_gares(gares: list, conn) -> int:
    if not gares:
        return 0
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO points_interet (type, nom, commune_code, latitude, longitude, geom)
               VALUES %s ON CONFLICT DO NOTHING""",
            [
                ("gare", g["nom"], g["commune_code"], g["latitude"], g["longitude"],
                 f"SRID=4326;POINT({g['longitude']} {g['latitude']})")
                for g in gares
            ],
        )
    conn.commit()
    return len(gares)


# ── Écoles Overpass ───────────────────────────────────────────────────────────

def overpass_query(query: str, retries: int = 3) -> list:
    payload = urllib.parse.urlencode({"data": query})
    for attempt in range(retries):
        for base in OVERPASS:
            try:
                r = requests.post(base, data=payload, headers=HEADERS_OVP, timeout=300)
                if r.status_code == 200:
                    return r.json().get("elements", [])
                log.warning("  HTTP %d sur %s", r.status_code, base.split("/")[2])
            except requests.exceptions.Timeout:
                log.warning("  Timeout %s — essai suivant", base.split("/")[2])
            except Exception as e:
                log.warning("  %s : %s", base.split("/")[2], e)
            time.sleep(3)
        if attempt < retries - 1:
            wait = 20 * (attempt + 1)
            log.info("  Pause %ds avant retry %d/%d …", wait, attempt + 2, retries)
            time.sleep(wait)
    return []


def inserer_ecoles(elements: list, conn) -> int:
    batch = []
    for el in elements:
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lng = el.get("lon") or (el.get("center") or {}).get("lon")
        if not lat or not lng:
            continue
        nom = (el.get("tags") or {}).get("name", "")
        batch.append(("ecole", nom, float(lat), float(lng)))
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


# ── Pipeline par département ──────────────────────────────────────────────────

def charger_poi(dept: str, toutes_gares: list, conn) -> tuple[int, int]:
    bbox = BBOXES.get(dept.zfill(2))
    if not bbox:
        log.warning("[%s] Pas de bbox définie — skippé", dept)
        return 0, 0

    # Gares SNCF (filtrage local, pas d'API)
    gares_dept = filtrer_gares_bbox(toutes_gares, bbox)
    n_g = inserer_gares(gares_dept, conn)
    log.info("[%s] ✓ %d gares SNCF", dept, n_g)

    # Écoles (Overpass)
    bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    els_e = overpass_query(f"""
        [out:json][timeout:120];
        (node["amenity"="school"]({bbox_str});way["amenity"="school"]({bbox_str}););
        out center;
    """)
    n_e = inserer_ecoles(els_e, conn)
    log.info("[%s] ✓ %d écoles", dept, n_e)

    return n_g, n_e


def main():
    log.info("POI — %d départements", len(config.DEPARTEMENTS))
    conn = get_conn()

    # Charger TOUTES les gares SNCF une seule fois
    toutes_gares = charger_toutes_gares_sncf()

    tot_g = tot_e = 0
    for dept in config.DEPARTEMENTS:
        try:
            g, e = charger_poi(dept, toutes_gares, conn)
            tot_g += g
            tot_e += e
        except Exception as ex:
            log.error("[%s] %s", dept, ex)

    conn.close()
    log.info("TOTAL %d gares | %d écoles", tot_g, tot_e)


if __name__ == "__main__":
    main()
