"""
Chargement des indicateurs de loyers par commune (source Ministère de la Transition Écologique).
Lance : python scripts/load_loyers.py
"""
import csv
import io
import logging
import sys
import requests
from pathlib import Path

# Configuration du chemin d'importation relatif à la racine du projet
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts._db import get_conn
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("loyers")

# URLs des données de la Carte des loyers 2025
APPARTEMENT_CSV_URL = "https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-145010/pred-app-mef-dhup.csv"
MAISON_CSV_URL = "https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-145039/pred-mai-mef-dhup.csv"

def parse_float(val_str):
    if not val_str:
        return None
    try:
        return float(val_str.replace(",", ".").strip())
    except ValueError:
        return None

def download_csv_data(url):
    log.info("Téléchargement du fichier CSV...")
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=60)
    r.raise_for_status()
    return r.text

def main():
    log.info("LOYERS — Démarrage du chargement")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 1. Création de la table communes_loyers
            log.info("Création de la table communes_loyers si elle n'existe pas...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS communes_loyers (
                    commune_code VARCHAR(5) PRIMARY KEY,
                    nom_commune VARCHAR(255),
                    loyer_m2_appartement FLOAT,
                    loyer_m2_maison FLOAT
                );
            """)
            
            # 2. Récupération des codes communes cibles depuis communes_stats pour filtrer
            cur.execute("SELECT commune_code FROM communes_stats;")
            target_communes = {r[0] for r in cur.fetchall()}
            log.info("%d communes cibles récupérées pour le filtrage (ex: Nantes, Vannes, etc.).", len(target_communes))
            
            if not target_communes:
                log.warning("Aucune commune cible trouvée dans communes_stats. Chargement de toutes les communes...")

            rent_data = {}

            # 3. Téléchargement et parsing des appartements
            app_csv_content = download_csv_data(APPARTEMENT_CSV_URL)
            f = io.StringIO(app_csv_content)
            reader = csv.DictReader(f, delimiter=';')
            log.info("Traitement des loyers d'appartements...")
            for row in reader:
                commune_code = row.get("INSEE_C", "").strip()
                if target_communes and commune_code not in target_communes:
                    continue
                loyer_app = parse_float(row.get("loypredm2"))
                nom_commune = row.get("LIBGEO", "").strip()
                
                if commune_code:
                    rent_data[commune_code] = {
                        "nom": nom_commune,
                        "loyer_app": loyer_app,
                        "loyer_maison": None
                    }

            # 4. Téléchargement et parsing des maisons
            maison_csv_content = download_csv_data(MAISON_CSV_URL)
            f = io.StringIO(maison_csv_content)
            reader = csv.DictReader(f, delimiter=';')
            log.info("Traitement des loyers de maisons...")
            for row in reader:
                commune_code = row.get("INSEE_C", "").strip()
                if target_communes and commune_code not in target_communes:
                    continue
                loyer_maison = parse_float(row.get("loypredm2"))
                nom_commune = row.get("LIBGEO", "").strip()
                
                if commune_code:
                    if commune_code in rent_data:
                        rent_data[commune_code]["loyer_maison"] = loyer_maison
                    else:
                        rent_data[commune_code] = {
                            "nom": nom_commune,
                            "loyer_app": None,
                            "loyer_maison": loyer_maison
                        }

            # 5. Insertion en lot (bulk)
            log.info("Préparation de l'insertion en lot de %d communes...", len(rent_data))
            insert_args = [
                (code, data["nom"], data["loyer_app"], data["loyer_maison"])
                for code, data in rent_data.items()
            ]
            
            query_sql = """
                INSERT INTO communes_loyers (commune_code, nom_commune, loyer_m2_appartement, loyer_m2_maison)
                VALUES %s
                ON CONFLICT (commune_code) DO UPDATE
                SET nom_commune = EXCLUDED.nom_commune,
                    loyer_m2_appartement = COALESCE(EXCLUDED.loyer_m2_appartement, communes_loyers.loyer_m2_appartement),
                    loyer_m2_maison = COALESCE(EXCLUDED.loyer_m2_maison, communes_loyers.loyer_m2_maison);
            """
            
            execute_values(cur, query_sql, insert_args)
            conn.commit()
            log.info("✓ TOTAL %d lignes de loyers insérées/mises à jour en lot avec succès !", len(insert_args))

    except Exception as e:
        conn.rollback()
        log.error("Erreur durant l'ingestion des loyers : %s", e)
        raise e
    finally:
        conn.close()

if __name__ == "__main__":
    main()
