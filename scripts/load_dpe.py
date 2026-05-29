"""
Chargement des DPE ADEME — pagination API directe vers PostgreSQL.
Lance : python scripts/load_dpe.py
Durée : ~15 min par département → ~2h15 total
"""
import logging, re, sys, time, unicodedata, urllib.parse
from pathlib import Path
import psycopg2.extras
import requests
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts import config
from scripts._db import get_conn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("dpe")

DATASET_URL   = "https://data.ademe.fr/data-fair/api/v1/datasets/meg-83tjwtg8dyz4vv7h1dqe/lines"
CLASSES_OK    = set("ABCDEFG")


def normaliser(addr: str) -> str:
    if not addr:
        return ""
    a = unicodedata.normalize("NFD", addr.lower().strip())
    a = "".join(c for c in a if unicodedata.category(c) != "Mn")
    a = re.sub(r"\s+\d{5}\b.*$", "", a)
    for p, r_ in {r"\br\b": "rue", r"\bav\b": "avenue", r"\bbd\b": "boulevard"}.items():
        a = re.sub(p, r_, a)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", a)).strip()


def charger_dpe(dept: str, conn) -> int:
    # Supprimer les DPE existants pour ce département (idempotent)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM dpe WHERE commune_code LIKE %s", (f"{dept}%",))
        deleted = cur.rowcount
    conn.commit()
    if deleted:
        log.info("  %d DPE existants supprimés [%s]", deleted, dept)

    after    = None
    page     = 0
    inserted = 0
    batch    = []

    def flush():
        nonlocal inserted
        if not batch:
            return
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO dpe
                   (numero_dpe,commune_code,adresse,adresse_normalisee,
                    classe_energie,conso_energie,classe_ges,annee_dpe,
                    type_batiment,annee_construction,
                    latitude,longitude,geom)
                   VALUES %s""",
                batch,
                template="""(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    CASE WHEN %s IS NOT NULL AND %s IS NOT NULL
                         THEN ST_SetSRID(ST_MakePoint(%s,%s),4326) ELSE NULL END)""",
                page_size=1000,
            )
        conn.commit()
        inserted += len(batch)
        batch.clear()

    while True:
        params = {
            "size":   10_000,
            "select": "numero_dpe,code_insee_ban,adresse_ban,etiquette_dpe,"
                      "conso_5_usages_par_m2_ep,etiquette_ges,date_reception_dpe,"
                      "type_batiment,annee_construction,_geopoint",
            "qs":     f"code_departement_ban:{dept}",
        }
        if after:
            params["after"] = after

        try:
            r = requests.get(DATASET_URL, params=params, timeout=60)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            log.warning("  Erreur page %d : %s", page, e)
            break

        results = data.get("results", [])
        if not results:
            break

        for row in results:
            classe = str(row.get("etiquette_dpe") or "").strip().upper()
            if classe not in CLASSES_OK:
                continue
            code    = str(row.get("code_insee_ban") or "").strip().zfill(5)
            adresse = str(row.get("adresse_ban") or "").strip()
            conso_r = row.get("conso_5_usages_par_m2_ep")
            try:
                conso = float(conso_r) if conso_r is not None else None
            except (ValueError, TypeError):
                conso = None
            date_d = str(row.get("date_reception_dpe") or "")
            annee_dpe = int(date_d[:4]) if len(date_d) >= 4 and date_d[:4].isdigit() else None
            # Année de construction (entier direct dans l'API)
            annee_c = row.get("annee_construction")
            try:
                annee_c = int(annee_c) if annee_c is not None else None
            except (ValueError, TypeError):
                annee_c = None
            # Coordonnées GPS depuis _geopoint ("lat,lon")
            geopoint = str(row.get("_geopoint") or "").strip()
            lat = lng = None
            if geopoint and "," in geopoint:
                try:
                    lat, lng = [float(x) for x in geopoint.split(",", 1)]
                except ValueError:
                    pass

            batch.append((
                str(row.get("numero_dpe") or ""), code, adresse,
                normaliser(adresse), classe, conso,
                str(row.get("etiquette_ges") or "").strip().upper() or None,
                annee_dpe,
                str(row.get("type_batiment") or "").strip().lower() or None,
                annee_c,
                lat, lng,          # latitude, longitude
                lat, lng, lng, lat, # pour CASE WHEN geom
            ))
            if len(batch) >= 2000:
                flush()

        page += 1
        total = data.get("total", "?")
        print(f"\r  [{dept}] {page * 10_000}/{total} DPE …", end="", flush=True)

        next_url = data.get("next")
        if not next_url:
            break
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(next_url).query)
        after = (qs.get("after") or [None])[0]
        if not after:
            break
        time.sleep(0.1)

    flush()
    print()
    log.info("  ✓ %d DPE insérés [%s]", inserted, dept)
    return inserted


def main():
    log.info("DPE — %d départements", len(config.DEPARTEMENTS))
    conn = get_conn()
    total = 0
    
    # Sécurité Idempotence
    for dept in config.DEPARTEMENTS:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM dpe WHERE commune_code LIKE %s LIMIT 1", (dept + '%',))
            if cur.fetchone() is not None:
                if getattr(config, 'FORCE_OVERWRITE', False):
                    log.warning("Suppression des anciens DPE pour %s...", dept)
                    cur.execute("DELETE FROM dpe WHERE commune_code LIKE %s", (dept + '%',))
                    conn.commit()
                else:
                    raise Exception(f"Les DPE pour le département {dept} existent déjà. Activez 'force_overwrite' dans Dagster pour les écraser.")
                    
    for dept in config.DEPARTEMENTS:
        try:
            total += charger_dpe(dept, conn)
        except Exception as e:
            log.error("[%s] %s", dept, e)
    conn.close()
    log.info("TOTAL %d DPE", total)


if __name__ == "__main__":
    main()
