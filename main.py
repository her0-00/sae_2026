#!/usr/bin/env python3
"""
Pipeline principal SAE 2026 — Outil décisionnel immobilier français.

Télécharge automatiquement toutes les données publiques, les ingère
dans PostgreSQL, enrichit les transactions et rafraîchit les vues analytiques.

Usage :
    python main.py                  # département 69 (Rhône), année 2024
    python main.py --dept 75        # Paris
    python main.py --dept 33 --annee 2023
"""
import argparse
import gzip
import io
import json
import logging
import os
import sys
import time
from pathlib import Path

import pandas as pd
import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

DSN = os.environ.get("DATABASE_URL")
if not DSN:
    sys.exit("DATABASE_URL manquant dans .env")

# ── Utilitaires ───────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(DSN)


def titre(msg: str):
    bar = "─" * 60
    log.info(bar)
    log.info("  %s", msg)
    log.info(bar)


def telecharger(url: str, dest: Path, desc: str) -> Path:
    if dest.exists():
        log.info("  [cache] %s déjà présent", dest.name)
        return dest
    log.info("  Téléchargement %s …", desc)
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    total = int(r.headers.get("content-length", 0))
    downloaded = 0
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded * 100 // total
                print(f"\r    {pct}% ({downloaded/1e6:.1f} MB / {total/1e6:.1f} MB)", end="", flush=True)
    print()
    log.info("  → %s sauvegardé", dest.name)
    return dest


def normaliser_adresse(addr: str) -> str:
    if not addr:
        return ""
    import unicodedata, re
    addr = addr.lower().strip()
    addr = unicodedata.normalize("NFD", addr)
    addr = "".join(c for c in addr if unicodedata.category(c) != "Mn")
    # Supprimer le code postal et la ville (ex: "69007 lyon" dans les adresses DPE)
    addr = re.sub(r"\s+\d{5}\b.*$", "", addr)
    abbrevs = {r"\br\b": "rue", r"\bav\b": "avenue", r"\bbd\b": "boulevard",
               r"\bimp\b": "impasse", r"\bpl\b": "place", r"\ball\b": "allee",
               r"\bchem\b": "chemin"}
    for pat, rep in abbrevs.items():
        addr = re.sub(pat, rep, addr)
    addr = re.sub(r"[^a-z0-9 ]", " ", addr)
    return re.sub(r"\s+", " ", addr).strip()


# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 1 — Communes + contours géographiques  (API Géo IGN)
# ══════════════════════════════════════════════════════════════════════════════

def etape_communes(dept: str):
    titre(f"Étape 1 — Communes du département {dept}")

    url = (
        f"https://geo.api.gouv.fr/communes"
        f"?codeDepartement={dept}&format=geojson&geometry=contour&limit=2000"
    )
    dest = DATA_DIR / f"communes_{dept}.geojson"

    log.info("  Téléchargement communes via API Géo …")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    geojson = r.json()
    dest.write_text(json.dumps(geojson), encoding="utf-8")
    log.info("  %d communes récupérées", len(geojson.get("features", [])))

    conn = get_conn()
    inserted = 0
    with conn.cursor() as cur:
        for feat in geojson.get("features", []):
            props = feat["properties"]
            geom  = feat.get("geometry")
            code  = props.get("code", "")
            nom   = props.get("nom", "")
            if not code or not geom:
                continue
            geom_str = json.dumps(geom)
            cur.execute(
                """
                INSERT INTO communes_stats (commune_code, nom_commune, departement_code, geom)
                VALUES (%s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                ON CONFLICT (commune_code) DO UPDATE
                    SET nom_commune      = EXCLUDED.nom_commune,
                        departement_code = EXCLUDED.departement_code,
                        geom             = EXCLUDED.geom
                """,
                (code, nom, dept, geom_str),
            )
            inserted += 1
    conn.commit()
    conn.close()
    log.info("  ✓ %d communes insérées/mises à jour", inserted)


# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 2 — Transactions DVF géolocalisées  (geo-dvf data.gouv.fr)
# ══════════════════════════════════════════════════════════════════════════════

def etape_dvf(dept: str, annee: int):
    titre(f"Étape 2 — DVF géolocalisé {dept} / {annee}")

    url  = f"https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/{dept}.csv.gz"
    dest = DATA_DIR / f"dvf_{dept}_{annee}.csv.gz"
    telecharger(url, dest, f"DVF {dept} {annee}")

    TYPES_VALIDES = {"Appartement", "Maison", "Local industriel. commercial ou assimilé"}

    log.info("  Lecture et nettoyage …")
    chunks = []
    with gzip.open(dest, "rt", encoding="utf-8") as f:
        for chunk in pd.read_csv(f, dtype=str, chunksize=50_000, low_memory=False):
            chunk = chunk[chunk["type_local"].isin(TYPES_VALIDES)].copy()
            chunks.append(chunk)

    if not chunks:
        log.warning("  Aucune ligne valide dans le fichier DVF")
        return

    df = pd.concat(chunks, ignore_index=True)
    log.info("  %d lignes après filtre type local", len(df))

    df["valeur_fonciere"]          = pd.to_numeric(df.get("valeur_fonciere", pd.Series(dtype=float)), errors="coerce")
    df["surface_reelle_bati"]      = pd.to_numeric(df.get("surface_reelle_bati", pd.Series(dtype=float)), errors="coerce")
    df["nombre_pieces_principales"]= pd.to_numeric(df.get("nombre_pieces_principales", pd.Series(dtype=float)), errors="coerce")
    df["longitude"] = pd.to_numeric(df.get("longitude", pd.Series(dtype=float)), errors="coerce")
    df["latitude"]  = pd.to_numeric(df.get("latitude",  pd.Series(dtype=float)), errors="coerce")

    num  = df.get("adresse_numero",    pd.Series(dtype=str)).fillna("")
    voie = df.get("adresse_nom_voie",  pd.Series(dtype=str)).fillna("")
    df["adresse"]            = (num + " " + voie).str.strip()
    df["adresse_normalisee"] = df["adresse"].apply(normaliser_adresse)
    df["prix_m2"]            = (df["valeur_fonciere"] / df["surface_reelle_bati"].replace(0, None)).round(2)
    df["code_commune"]       = df.get("code_commune", pd.Series(dtype=str)).fillna("").str.strip().str.zfill(5)

    # Dédoublonnage — une transaction par id_mutation
    df = df.drop_duplicates(subset=["id_mutation"])

    # Filtres outliers
    masque = (
        df["valeur_fonciere"].between(1_000, 50_000_000)
        & df["surface_reelle_bati"].between(5, 10_000)
        & df["prix_m2"].between(100, 50_000)
    )
    log.info("  %d transactions rejetées (outliers)", (~masque).sum())
    df = df[masque].copy()
    log.info("  %d transactions valides à insérer", len(df))

    # Supprimer les données existantes pour ce dept+année (idempotent)
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM transactions WHERE departement_code = %s "
            "AND date_mutation >= %s AND date_mutation < %s",
            (dept, f"{annee}-01-01", f"{annee+1}-01-01"),
        )
        log.info("  %d transactions existantes supprimées (re-run propre)", cur.rowcount)
    conn.commit()

    # Insertion par batch (pas besoin de ON CONFLICT)
    inserted = 0
    rows_batch = []

    def flush(batch):
        if not batch:
            return 0
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO transactions
                    (id_mutation, date_mutation, commune_code, departement_code,
                     adresse, adresse_normalisee, code_postal, type_local,
                     surface_bati, nb_pieces, valeur_fonciere, prix_m2,
                     latitude, longitude, geom)
                VALUES %s
                """,
                batch,
                template="""(
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s IS NOT NULL AND %s IS NOT NULL
                         THEN ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                         ELSE NULL END
                )""",
                page_size=1000,
            )
        conn.commit()
        return len(batch)

    for _, row in df.iterrows():
        lat = row.get("latitude")
        lng = row.get("longitude")
        lat = float(lat) if pd.notna(lat) else None
        lng = float(lng) if pd.notna(lng) else None
        rows_batch.append((
            row.get("id_mutation"),
            row.get("date_mutation"),
            row.get("code_commune"),
            dept,
            row.get("adresse"),
            row.get("adresse_normalisee"),
            row.get("code_postal"),
            row.get("type_local"),
            row.get("surface_reelle_bati")       if pd.notna(row.get("surface_reelle_bati")) else None,
            int(row["nombre_pieces_principales"]) if pd.notna(row.get("nombre_pieces_principales")) else None,
            row.get("valeur_fonciere")            if pd.notna(row.get("valeur_fonciere")) else None,
            row.get("prix_m2")                   if pd.notna(row.get("prix_m2")) else None,
            lat, lng,
            lat, lng, lng, lat,  # pour CASE WHEN dans le template
        ))
        if len(rows_batch) >= 2000:
            inserted += flush(rows_batch)
            rows_batch = []
            print(f"\r    {inserted}/{len(df)} insérés …", end="", flush=True)

    inserted += flush(rows_batch)
    print()
    conn.close()
    log.info("  ✓ %d transactions insérées", inserted)


# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 3 — DPE  (ADEME open data — téléchargement CSV direct par département)
# ══════════════════════════════════════════════════════════════════════════════

def etape_dpe(dept: str):
    titre(f"Étape 3 — DPE département {dept}")
    CLASSES = set("ABCDEFG")

    # ID vérifié via https://data.ademe.fr/data-fair/api/v1/datasets?q=dpe
    DATASET_ID = "meg-83tjwtg8dyz4vv7h1dqe"  # DPE Logements existants (depuis juillet 2021)
    BASE_ADEME = "https://data.ademe.fr/data-fair/api/v1/datasets"
    dataset_url = f"{BASE_ADEME}/{DATASET_ID}/lines"

    dest = DATA_DIR / f"dpe_{dept}.jsonl"
    if dest.exists():
        log.info("  [cache] DPE déjà téléchargé")
    else:
        try:
            requests.get(f"{dataset_url}?size=1", timeout=15).raise_for_status()
        except Exception as e:
            log.warning("  API ADEME inaccessible (%s) — DPE ignoré", e)
            dest.write_text("", encoding="utf-8")
            return
        log.info("  Téléchargement DPE via API ADEME (pagination) …")
        all_rows = []
        after = None
        page  = 0
        import urllib.parse

        while True:
            # Colonnes réelles du nouveau dataset (tout en minuscules)
            params = {
                "size":     10_000,
                "select":   "numero_dpe,code_insee_ban,adresse_ban,etiquette_dpe,"
                            "conso_5_usages_par_m2_ep,etiquette_ges,date_reception_dpe,type_batiment",
                "qs":       f"code_departement_ban:{dept}",
            }
            if after:
                params["after"] = after
            try:
                r = requests.get(dataset_url, params=params, timeout=60)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                log.warning("  Erreur ADEME page %d : %s", page, e)
                break

            results = data.get("results", [])
            all_rows.extend(results)
            page += 1
            print(f"\r    Page {page} — {len(all_rows)} / {data.get('total', '?')} DPE …", end="", flush=True)

            next_url = data.get("next")
            if not next_url or not results:
                break
            qs_parsed = urllib.parse.parse_qs(urllib.parse.urlparse(next_url).query)
            after = (qs_parsed.get("after") or [None])[0]
            if not after:
                break
            time.sleep(0.1)

        print()
        dest.write_text("\n".join(json.dumps(r) for r in all_rows), encoding="utf-8")
        log.info("  %d DPE sauvegardés", len(all_rows))

    lines = [json.loads(l) for l in dest.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        log.info("  Aucun DPE à insérer")
        return

    log.info("  Insertion de %d DPE …", len(lines))
    conn = get_conn()
    batch = []
    inserted = 0

    def flush_dpe(b):
        if not b:
            return 0
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO dpe (numero_dpe, commune_code, adresse, adresse_normalisee,
                                   classe_energie, conso_energie, classe_ges, annee_dpe)
                   VALUES %s ON CONFLICT DO NOTHING""",
                b, page_size=1000,
            )
        conn.commit()
        return len(b)

    for row in lines:
        # Nouveaux noms de colonnes (minuscules)
        classe     = str(row.get("etiquette_dpe", "") or "").strip().upper()
        if classe not in CLASSES:
            continue
        code_insee = str(row.get("code_insee_ban", "") or "").strip().zfill(5)
        adresse    = str(row.get("adresse_ban", "") or "").strip()
        conso_raw  = row.get("conso_5_usages_par_m2_ep")
        try:
            conso = float(conso_raw) if conso_raw is not None else None
        except (ValueError, TypeError):
            conso = None
        date_dpe  = str(row.get("date_reception_dpe", "") or "")
        annee_dpe = int(date_dpe[:4]) if len(date_dpe) >= 4 and date_dpe[:4].isdigit() else None
        batch.append((
            str(row.get("numero_dpe", "") or ""), code_insee, adresse,
            normaliser_adresse(adresse), classe, conso,
            str(row.get("etiquette_ges", "") or "").strip().upper() or None, annee_dpe,
        ))
        if len(batch) >= 2000:
            inserted += flush_dpe(batch); batch = []

    inserted += flush_dpe(batch)
    conn.close()
    log.info("  ✓ %d DPE insérés", inserted)


# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 4 — Gares (Overpass API / OpenStreetMap)
# ══════════════════════════════════════════════════════════════════════════════

def overpass_query(query: str, dest: Path, desc: str) -> list:
    """Exécute une requête Overpass et retourne les éléments JSON."""
    if dest.exists():
        log.info("  [cache] %s", dest.name)
        return json.loads(dest.read_text(encoding="utf-8")).get("elements", [])

    instances = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.openstreetmap.ru/api/interpreter",
    ]
    import urllib.parse
    payload = urllib.parse.urlencode({"data": query})
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    for base in instances:
        log.info("  Requête Overpass (%s) via %s …", desc, base.split("/")[2])
        try:
            r = requests.post(base, data=payload, headers=headers, timeout=120)
            if r.status_code == 200:
                dest.write_bytes(r.content)
                return r.json().get("elements", [])
            log.warning("  → HTTP %d, essai suivant …", r.status_code)
        except Exception as e:
            log.warning("  → Erreur : %s, essai suivant …", e)
        time.sleep(2)

    log.warning("  Toutes les instances Overpass ont échoué — %s ignoré", desc)
    return []


def etape_gares(dept: str):
    titre(f"Étape 4 — Gares ferroviaires département {dept}")

    BBOXES = {
        "01": (45.75,4.75,46.53,5.77),  "06": (43.45,6.63,44.36,7.72),
        "13": (43.15,4.24,43.93,5.81),  "14": (48.69,-1.12,49.54,0.50),
        "21": (46.74,4.07,48.07,5.64),  "25": (46.63,5.84,47.77,7.07),
        "29": (47.73,-5.16,48.80,-3.31),"31": (42.67,0.60,44.00,2.22),
        "33": (44.20,-1.24,45.58,0.34), "34": (43.23,2.84,44.08,4.24),
        "35": (47.63,-2.01,48.72,-0.92),"38": (44.71,4.77,45.96,6.36),
        "44": (46.88,-2.56,47.83,-1.04),"45": (47.49,1.53,48.27,3.11),
        "57": (48.80,6.08,49.83,7.63),  "59": (50.02,2.52,51.09,4.24),
        "62": (50.02,1.56,51.02,3.19),  "63": (45.07,2.50,46.27,3.95),
        "67": (47.42,6.84,49.08,8.24),  "69": (45.46,4.54,46.30,5.16),
        "75": (48.82,2.22,48.90,2.47),  "76": (49.26,0.04,50.07,1.82),
        "77": (48.12,2.39,49.12,3.56),  "78": (48.48,1.44,49.09,2.24),
        "83": (43.01,5.67,43.97,6.94),  "87": (45.38,0.88,46.37,2.26),
        "91": (48.27,1.90,48.78,2.58),  "92": (48.79,2.14,48.95,2.34),
        "93": (48.83,2.30,48.97,2.60),  "94": (48.71,2.31,48.87,2.58),
        "95": (48.93,1.60,49.27,2.63),
    }
    bbox = BBOXES.get(dept.zfill(2))
    if not bbox:
        log.warning("  Pas de bounding box pour dept %s — gares ignorées", dept)
        return

    bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    query = f"""
    [out:json][timeout:90];
    (
      node["railway"="station"]({bbox_str});
      node["railway"="halt"]({bbox_str});
    );
    out body;
    """
    elements = overpass_query(query, DATA_DIR / f"gares_{dept}.json", "gares")
    if not elements:
        return

    conn = get_conn()
    batch = [
        ("gare",
         (el.get("tags") or {}).get("name", ""),
         float(el["lat"]), float(el["lon"]))
        for el in elements if "lat" in el and "lon" in el
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO points_interet (type, nom, latitude, longitude, geom) VALUES %s ON CONFLICT DO NOTHING",
            [(t, n, lat, lng, f"SRID=4326;POINT({lng} {lat})") for t, n, lat, lng in batch],
        )
    conn.commit()
    conn.close()
    log.info("  ✓ %d gares insérées", len(batch))


# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 5 — Écoles  (Overpass API / OpenStreetMap)
# ══════════════════════════════════════════════════════════════════════════════

def etape_ecoles(dept: str):
    titre(f"Étape 5 — Écoles département {dept}")

    BBOXES = {
        "01": (45.75,4.75,46.53,5.77),  "06": (43.45,6.63,44.36,7.72),
        "13": (43.15,4.24,43.93,5.81),  "14": (48.69,-1.12,49.54,0.50),
        "21": (46.74,4.07,48.07,5.64),  "25": (46.63,5.84,47.77,7.07),
        "29": (47.73,-5.16,48.80,-3.31),"31": (42.67,0.60,44.00,2.22),
        "33": (44.20,-1.24,45.58,0.34), "34": (43.23,2.84,44.08,4.24),
        "35": (47.63,-2.01,48.72,-0.92),"38": (44.71,4.77,45.96,6.36),
        "44": (46.88,-2.56,47.83,-1.04),"45": (47.49,1.53,48.27,3.11),
        "57": (48.80,6.08,49.83,7.63),  "59": (50.02,2.52,51.09,4.24),
        "62": (50.02,1.56,51.02,3.19),  "63": (45.07,2.50,46.27,3.95),
        "67": (47.42,6.84,49.08,8.24),  "69": (45.46,4.54,46.30,5.16),
        "75": (48.82,2.22,48.90,2.47),  "76": (49.26,0.04,50.07,1.82),
        "77": (48.12,2.39,49.12,3.56),  "78": (48.48,1.44,49.09,2.24),
        "83": (43.01,5.67,43.97,6.94),  "87": (45.38,0.88,46.37,2.26),
        "91": (48.27,1.90,48.78,2.58),  "92": (48.79,2.14,48.95,2.34),
        "93": (48.83,2.30,48.97,2.60),  "94": (48.71,2.31,48.87,2.58),
        "95": (48.93,1.60,49.27,2.63),
    }
    bbox = BBOXES.get(dept.zfill(2))
    if not bbox:
        log.warning("  Pas de bounding box pour dept %s — écoles ignorées", dept)
        return

    bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    query = f"""
    [out:json][timeout:90];
    (
      node["amenity"="school"]({bbox_str});
      way["amenity"="school"]({bbox_str});
    );
    out center;
    """
    elements = overpass_query(query, DATA_DIR / f"ecoles_{dept}.json", "écoles")
    if not elements:
        return

    conn = get_conn()
    batch = []
    for el in elements:
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lng = el.get("lon") or (el.get("center") or {}).get("lon")
        if not lat or not lng:
            continue
        nom = (el.get("tags") or {}).get("name", "")
        batch.append(("ecole", nom, float(lat), float(lng)))

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO points_interet (type, nom, latitude, longitude, geom) VALUES %s ON CONFLICT DO NOTHING",
            [(t, n, lat, lng, f"SRID=4326;POINT({lng} {lat})") for t, n, lat, lng in batch],
        )
    conn.commit()
    conn.close()
    log.info("  ✓ %d écoles insérées", len(batch))


# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 6 — Enrichissement DPE (jointure adresse)
# ══════════════════════════════════════════════════════════════════════════════

def etape_enrich_dpe():
    titre("Étape 6 — Enrichissement transactions ← DPE")
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE transactions t
            SET dpe_classe = d.classe_energie,
                dpe_conso  = d.conso_energie
            FROM (
                SELECT DISTINCT ON (commune_code, adresse_normalisee)
                    commune_code, adresse_normalisee, classe_energie, conso_energie
                FROM dpe
                WHERE classe_energie IS NOT NULL
                ORDER BY commune_code, adresse_normalisee, annee_dpe DESC NULLS LAST
            ) d
            WHERE t.commune_code       = d.commune_code
              AND t.adresse_normalisee = d.adresse_normalisee
              AND t.dpe_classe IS NULL
        """)
        n = cur.rowcount
    conn.commit()
    conn.close()
    log.info("  ✓ %d transactions enrichies avec classe DPE", n)


# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 7 — Calcul distances gares & écoles
# ══════════════════════════════════════════════════════════════════════════════

def etape_distances():
    titre("Étape 7 — Calcul distances (gares & écoles)")
    conn = get_conn()
    with conn.cursor() as cur:
        # Distance gare
        cur.execute("""
            UPDATE transactions t
            SET dist_gare_m = (
                SELECT ST_Distance(t.geom::geography, p.geom::geography)::integer
                FROM points_interet p
                WHERE p.type = 'gare'
                ORDER BY t.geom <-> p.geom
                LIMIT 1
            )
            WHERE t.geom IS NOT NULL AND t.dist_gare_m IS NULL
        """)
        log.info("  ✓ %d transactions — distance gare calculée", cur.rowcount)

        # Distance école
        cur.execute("""
            UPDATE transactions t
            SET dist_ecole_m = (
                SELECT ST_Distance(t.geom::geography, p.geom::geography)::integer
                FROM points_interet p
                WHERE p.type = 'ecole'
                ORDER BY t.geom <-> p.geom
                LIMIT 1
            )
            WHERE t.geom IS NOT NULL AND t.dist_ecole_m IS NULL
        """)
        log.info("  ✓ %d transactions — distance école calculée", cur.rowcount)

    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 8 — Rafraîchissement des vues matérialisées
# ══════════════════════════════════════════════════════════════════════════════

def etape_refresh_vues():
    titre("Étape 8 — Rafraîchissement des vues matérialisées")
    vues = ["prix_m2_par_commune", "stats_dpe", "stats_peb", "stats_distance_gare"]
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        for vue in vues:
            log.info("  REFRESH %s …", vue)
            cur.execute(f"REFRESH MATERIALIZED VIEW {vue}")
            log.info("    → OK")
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 9 — Checks qualité
# ══════════════════════════════════════════════════════════════════════════════

def etape_quality():
    titre("Étape 9 — Checks qualité")
    checks = [
        ("nb_transactions",      "SELECT COUNT(*) FROM transactions WHERE est_valide = TRUE"),
        ("nb_geocodees",         "SELECT COUNT(*) FROM transactions WHERE geom IS NOT NULL"),
        ("nb_avec_dpe",          "SELECT COUNT(*) FROM transactions WHERE dpe_classe IS NOT NULL"),
        ("nb_communes",          "SELECT COUNT(*) FROM communes_stats"),
        ("nb_communes_avec_geom","SELECT COUNT(*) FROM communes_stats WHERE geom IS NOT NULL"),
        ("nb_gares",             "SELECT COUNT(*) FROM points_interet WHERE type = 'gare'"),
        ("nb_ecoles",            "SELECT COUNT(*) FROM points_interet WHERE type = 'ecole'"),
        ("nb_dpe",               "SELECT COUNT(*) FROM dpe"),
    ]
    conn = get_conn()
    resultats = {}
    with conn.cursor() as cur:
        for name, sql in checks:
            cur.execute(sql)
            resultats[name] = cur.fetchone()[0]

    conn.close()

    log.info("")
    log.info("  ┌─────────────────────────────────────────┐")
    log.info("  │         RÉSUMÉ DE LA BASE               │")
    log.info("  ├─────────────────────────────────────────┤")
    for k, v in resultats.items():
        log.info("  │  %-30s %8s │", k, f"{v:,}")

    n = resultats["nb_transactions"]
    geo = resultats["nb_geocodees"]
    dpe = resultats["nb_avec_dpe"]
    taux_geo = (geo / n * 100) if n else 0
    taux_dpe = (dpe / n * 100) if n else 0
    log.info("  ├─────────────────────────────────────────┤")
    log.info("  │  Taux géocodage                %6.1f %%  │", taux_geo)
    log.info("  │  Taux DPE                      %6.1f %%  │", taux_dpe)
    log.info("  └─────────────────────────────────────────┘")
    log.info("")

    # Stocker dans quality_log
    conn2 = get_conn()
    with conn2.cursor() as cur:
        for k, v in resultats.items():
            cur.execute(
                "INSERT INTO quality_log (check_name, passed, value, details) VALUES (%s, %s, %s, %s)",
                (k, v > 0, float(v), f"run pipeline dept={args_global.dept if args_global else 'unknown'}"),
            )
    conn2.commit()
    conn2.close()


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

args_global = None

def main():
    global args_global
    parser = argparse.ArgumentParser(description="Pipeline SAE 2026")
    parser.add_argument("--dept",  default="69",  help="Code département (défaut : 69)")
    parser.add_argument("--annee", default=2024,  type=int, help="Année DVF (défaut : 2024)")
    parser.add_argument("--skip",  nargs="*", default=[], help="Étapes à sauter ex: --skip dpe ecoles")
    args = parser.parse_args()
    args_global = args

    t0 = time.time()
    log.info("═" * 62)
    log.info("  PIPELINE SAE 2026 — Département %s / Année %s", args.dept, args.annee)
    log.info("═" * 62)

    etapes = {
        "communes": lambda: etape_communes(args.dept),
        "dvf":      lambda: etape_dvf(args.dept, args.annee),
        "dpe":      lambda: etape_dpe(args.dept),
        "gares":    lambda: etape_gares(args.dept),
        "ecoles":   lambda: etape_ecoles(args.dept),
        "enrich_dpe":  lambda: etape_enrich_dpe(),
        "distances":   lambda: etape_distances(),
        "vues":        lambda: etape_refresh_vues(),
        "quality":     lambda: etape_quality(),
    }

    for nom, fn in etapes.items():
        if nom in args.skip:
            log.info("  [skip] %s", nom)
            continue
        try:
            fn()
        except Exception as e:
            log.error("  ✗ Étape '%s' échouée : %s", nom, e)
            log.exception(e)
            log.warning("  → Pipeline continue malgré l'erreur")

    duree = time.time() - t0
    log.info("═" * 62)
    log.info("  Pipeline terminé en %.1f secondes (%.1f min)", duree, duree / 60)
    log.info("═" * 62)


if __name__ == "__main__":
    main()
