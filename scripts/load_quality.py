"""
Journalisation de la qualité des données dans la table quality_log.
Lance : python scripts/load_quality.py
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts._db import get_conn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("quality")

def main():
    log.info("QUALITY — Démarrage du contrôle qualité")
    
    checks = [
        ("nb_transactions",        "SELECT COUNT(*) FROM transactions WHERE est_valide = TRUE", "Transactions valides"),
        ("nb_geocodees",           "SELECT COUNT(*) FROM transactions WHERE geom IS NOT NULL", "Transactions géocodées"),
        ("nb_avec_dpe",            "SELECT COUNT(*) FROM transactions WHERE dpe_classe IS NOT NULL", "Transactions avec DPE"),
        ("nb_avec_peb",            "SELECT COUNT(*) FROM transactions WHERE peb_zone IS NOT NULL", "Transactions en zone PEB"),
        ("nb_communes",            "SELECT COUNT(*) FROM communes_stats", "Communes chargées"),
        ("nb_communes_avec_geom",  "SELECT COUNT(*) FROM communes_stats WHERE geom IS NOT NULL", "Communes avec géométrie"),
        ("nb_gares",               "SELECT COUNT(*) FROM points_interet WHERE type = 'gare'", "Gares SNCF chargées"),
        ("nb_ecoles",              "SELECT COUNT(*) FROM points_interet WHERE type = 'ecole'", "Écoles chargées"),
        ("nb_dpe",                 "SELECT COUNT(*) FROM dpe", "Diagnostics DPE chargés"),
    ]
    
    conn = get_conn()
    resultats = {}
    
    try:
        with conn.cursor() as cur:
            for key, sql, label in checks:
                cur.execute(sql)
                val = cur.fetchone()[0]
                resultats[key] = (val, label)
                
            log.info("Persistance des métriques de qualité dans la table quality_log...")
            for key, (val, label) in resultats.items():
                cur.execute(
                    """
                    INSERT INTO quality_log (check_name, passed, value, details)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (key, val > 0, float(val), f"Modular run for Morbihan (56) - {label}")
                )
            conn.commit()
            log.info("✓ Métriques de qualité enregistrées avec succès !")
            
            log.info("")
            log.info("  ┌──────────────────────────────────────────┐")
            log.info("  │         RÉSUMÉ QUALITÉ DES DONNÉES       │")
            log.info("  ├──────────────────────────────────────────┤")
            for key, (val, label) in resultats.items():
                log.info("  │  %-28s %8s  │", label, f"{val:,}")
            log.info("  └──────────────────────────────────────────┘")
            log.info("")
            
    except Exception as e:
        conn.rollback()
        log.error("Erreur durant le contrôle qualité : %s", e)
        raise e
    finally:
        conn.close()

if __name__ == "__main__":
    main()
