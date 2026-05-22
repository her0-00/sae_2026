"""
Enrichissement de TOUTES les transactions : DPE, distances, refresh vues.
Lance : python scripts/load_enrichment.py
Durée : ~15 min
"""
import logging, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts._db import get_conn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("enrichment")


def enrich_dpe(conn):
    # Passe 1 : jointure exacte sur adresse_normalisee + commune_code
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE transactions t
            SET dpe_classe = d.classe_energie,
                dpe_conso  = d.conso_energie
            FROM (
                SELECT DISTINCT ON (commune_code, adresse_normalisee)
                    commune_code, adresse_normalisee, classe_energie, conso_energie
                FROM dpe
                WHERE classe_energie IS NOT NULL AND LENGTH(adresse_normalisee) > 5
                ORDER BY commune_code, adresse_normalisee, annee_dpe DESC NULLS LAST
            ) d
            WHERE t.commune_code       = d.commune_code
              AND t.adresse_normalisee = d.adresse_normalisee
              AND t.dpe_classe IS NULL
        """)
        n1 = cur.rowcount
    conn.commit()
    log.info("  Passe 1 (adresse exacte)   : %d transactions", n1)

    # Passe 2 : jointure spatiale — DPE le plus proche dans un rayon de 30m (approx 0.0003 deg)
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE transactions t
            SET dpe_classe = d.classe_energie,
                dpe_conso  = d.conso_energie
            FROM (
                SELECT DISTINCT ON (t2.id)
                    t2.id,
                    d2.classe_energie,
                    d2.conso_energie
                FROM transactions t2
                JOIN dpe d2
                  ON d2.geom IS NOT NULL
                  AND ST_DWithin(t2.geom, d2.geom, 0.0003)
                WHERE t2.geom IS NOT NULL
                  AND t2.dpe_classe IS NULL
                  AND d2.classe_energie IS NOT NULL
                ORDER BY t2.id, t2.geom <-> d2.geom
            ) d
            WHERE t.id = d.id
              AND t.dpe_classe IS NULL
        """)
        n2 = cur.rowcount
    conn.commit()
    log.info("  Passe 2 (proximité GPS 30m): %d transactions", n2)
    log.info("✓ DPE total : %d transactions enrichies", n1 + n2)


def enrich_distances(conn):
    with conn.cursor() as cur:
        # Check if we have gares
        cur.execute("SELECT 1 FROM points_interet WHERE type='gare' LIMIT 1")
        if cur.fetchone():
            cur.execute("""
                UPDATE transactions t SET dist_gare_m = (
                    SELECT ST_Distance(t.geom::geography, p.geom::geography)::integer
                    FROM points_interet p WHERE p.type='gare'
                    ORDER BY t.geom <-> p.geom LIMIT 1
                ) WHERE t.geom IS NOT NULL AND t.dist_gare_m IS NULL
            """)
            log.info("✓ Distances gares : %d", cur.rowcount)
        else:
            log.info("✓ Aucun point d'intérêt 'gare' trouvé dans points_interet. Saut de l'étape.")

        # Check if we have écoles
        cur.execute("SELECT 1 FROM points_interet WHERE type='ecole' LIMIT 1")
        if cur.fetchone():
            cur.execute("""
                UPDATE transactions t SET dist_ecole_m = (
                    SELECT ST_Distance(t.geom::geography, p.geom::geography)::integer
                    FROM points_interet p WHERE p.type='ecole'
                    ORDER BY t.geom <-> p.geom LIMIT 1
                ) WHERE t.geom IS NOT NULL AND t.dist_ecole_m IS NULL
            """)
            log.info("✓ Distances écoles : %d", cur.rowcount)
        else:
            log.info("✓ Aucun point d'intérêt 'ecole' trouvé dans points_interet. Saut de l'étape.")
    conn.commit()


def enrich_peb(conn):
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE transactions t
            SET peb_zone     = p.zone,
                peb_aeroport = p.aeroport
            FROM (
                SELECT DISTINCT ON (t2.id)
                    t2.id,
                    p2.zone,
                    p2.aeroport
                FROM transactions t2
                JOIN peb_zones p2 ON ST_Within(t2.geom, p2.geom)
                WHERE t2.geom IS NOT NULL AND t2.peb_zone IS NULL
                ORDER BY t2.id, p2.zone ASC
            ) p
            WHERE t.id = p.id
        """)
        log.info("✓ Enrichissement PEB : %d transactions", cur.rowcount)
    conn.commit()


def refresh_views(conn):
    conn.autocommit = True
    with conn.cursor() as cur:
        for vue in ["prix_m2_par_commune", "stats_dpe", "stats_peb", "stats_distance_gare"]:
            cur.execute(f"REFRESH MATERIALIZED VIEW {vue}")
            log.info("✓ REFRESH %s", vue)
    conn.autocommit = False


def rapport(conn):
    checks = [
        ("Transactions",             "SELECT COUNT(*) FROM transactions"),
        ("Geocodees",                "SELECT COUNT(*) FROM transactions WHERE geom IS NOT NULL"),
        ("Avec DPE",                 "SELECT COUNT(*) FROM transactions WHERE dpe_classe IS NOT NULL"),
        ("Avec PEB",                 "SELECT COUNT(*) FROM transactions WHERE peb_zone IS NOT NULL"),
        ("Avec dist. gare",          "SELECT COUNT(*) FROM transactions WHERE dist_gare_m IS NOT NULL"),
        ("Departements",             "SELECT COUNT(DISTINCT departement_code) FROM transactions"),
        ("Annees",                   "SELECT COUNT(DISTINCT EXTRACT(YEAR FROM date_mutation)) FROM transactions"),
        ("Communes enrichies",       "SELECT COUNT(*) FROM communes_stats WHERE revenu_median IS NOT NULL"),
        ("DPE",                      "SELECT COUNT(*) FROM dpe"),
    ]
    log.info("")
    log.info("  ┌──────────────────────────────────────────┐")
    log.info("  │              BILAN FINAL                 │")
    log.info("  ├──────────────────────────────────────────┤")
    with conn.cursor() as cur:
        for label, sql in checks:
            cur.execute(sql)
            log.info("  │  %-28s %8s  │", label, f"{cur.fetchone()[0]:,}")
    log.info("  └──────────────────────────────────────────┘")


def main():
    log.info("ENRICHISSEMENT GLOBAL")
    conn = get_conn()
    enrich_dpe(conn)
    enrich_distances(conn)
    enrich_peb(conn)
    refresh_views(conn)
    rapport(conn)
    conn.close()


if __name__ == "__main__":
    main()
