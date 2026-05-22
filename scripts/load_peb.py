"""
Chargement des zones PEB (Plans d'Exposition au Bruit) depuis data.gouv.fr.
Lance : python scripts/load_peb.py
"""
import json
import logging
import sys
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts._db import get_conn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("peb")

URLS = {
    "A": "https://static.data.gouv.fr/resources/zonage-des-plan-dexposition-au-bruit-peb/20200602-202334/c-dgac-peb-metro-za.geojson",
    "B": "https://static.data.gouv.fr/resources/zonage-des-plan-dexposition-au-bruit-peb/20200602-202306/c-dgac-peb-metro-zb.geojson",
    "C": "https://static.data.gouv.fr/resources/zonage-des-plan-dexposition-au-bruit-peb/20200602-202327/c-dgac-peb-metro-zc.geojson",
    "D": "https://static.data.gouv.fr/resources/zonage-des-plan-dexposition-au-bruit-peb/20200602-202316/c-dgac-peb-metro-zd.geojson"
}

def main():
    log.info("PEB — Démarrage du chargement")
    conn = get_conn()
    
    try:
        with conn.cursor() as cur:
            log.info("Nettoyage de la table peb_zones...")
            cur.execute("TRUNCATE TABLE peb_zones RESTART IDENTITY CASCADE;")
            
            inserted = 0
            for zone_code, url in URLS.items():
                log.info("Téléchargement du GeoJSON pour la zone %s...", zone_code)
                r = requests.get(url, timeout=60)
                r.raise_for_status()
                geojson = r.json()
                features = geojson.get("features", [])
                log.info("Zone %s : %d entités trouvées", zone_code, len(features))
                
                for feat in features:
                    props = feat.get("properties", {})
                    geom = feat.get("geometry")
                    if not geom:
                        continue
                    
                    # Récupération des propriétés
                    aeroport = props.get("NOM", "Aéroport inconnu")
                    code_icao = props.get("CODE_OACI", None)
                    zone = props.get("ZONE", zone_code)
                    
                    cur.execute(
                        """
                        INSERT INTO peb_zones (aeroport, code_icao, zone, geom)
                        VALUES (%s, %s, %s, ST_Multi(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%s), 2154), 4326)))
                        """,
                        (aeroport, code_icao, zone, json.dumps(geom))
                    )
                    inserted += 1
            
            conn.commit()
            log.info("✓ TOTAL %d zones PEB insérées avec succès !", inserted)
    except Exception as e:
        conn.rollback()
        log.error("Erreur durant l'ingestion PEB : %s", e)
        raise e
    finally:
        conn.close()

if __name__ == "__main__":
    main()
