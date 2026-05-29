"""
Chargement des contours géographiques des communes (API Géo IGN).
Lance : python scripts/load_communes.py
Durée : ~10 min
"""
import json, logging, sys
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts import config
from scripts._db import get_conn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("communes")


def charger_dept(dept: str, conn):
    url = f"https://geo.api.gouv.fr/communes?codeDepartement={dept}&format=geojson&geometry=contour&limit=2000"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    features = r.json().get("features", [])

    inserted = 0
    with conn.cursor() as cur:
        for feat in features:
            props      = feat["properties"]
            code       = props.get("code", "")
            nom        = props.get("nom", "")
            region     = props.get("codeRegion")        # ex: "84" (Auvergne-Rhône-Alpes)
            population = props.get("population")        # nombre d'habitants
            geom       = feat.get("geometry")
            if not code or not geom:
                continue
            cur.execute(
                """
                INSERT INTO communes_stats
                    (commune_code, nom_commune, departement_code, region_code, population, geom)
                VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                ON CONFLICT (commune_code) DO UPDATE
                    SET nom_commune      = EXCLUDED.nom_commune,
                        departement_code = EXCLUDED.departement_code,
                        region_code      = EXCLUDED.region_code,
                        population       = EXCLUDED.population,
                        geom             = EXCLUDED.geom
                """,
                (code, nom, dept, region, population, json.dumps(geom)),
            )
            inserted += 1
    conn.commit()
    log.info("[%s] ✓ %d communes", dept, inserted)
    return inserted


def main():
    log.info("COMMUNES — %d départements", len(config.DEPARTEMENTS))
    conn = get_conn()
    total = 0
    for dept in config.DEPARTEMENTS:
        try:
            total += charger_dept(dept, conn)
        except Exception as e:
            log.error("[%s] %s", dept, e)
    conn.close()
    log.info("TOTAL %d communes", total)


if __name__ == "__main__":
    main()
