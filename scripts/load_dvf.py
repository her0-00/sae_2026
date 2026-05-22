"""
Chargement des transactions DVF géolocalisées — streaming direct vers PostgreSQL.
Lance : python scripts/load_dvf.py
Durée : ~2h15 (9 depts × 5 ans)
"""
import gzip, io, logging, re, sys, unicodedata
from pathlib import Path
import pandas as pd
import psycopg2.extras
import requests
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.config import DEPARTEMENTS, ANNEES
from scripts._db import get_conn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("dvf")

TYPES_VALIDES = {"Appartement", "Maison", "Local industriel. commercial ou assimilé"}


def normaliser(addr: str) -> str:
    if not addr:
        return ""
    a = unicodedata.normalize("NFD", addr.lower().strip())
    a = "".join(c for c in a if unicodedata.category(c) != "Mn")
    a = re.sub(r"\s+\d{5}\b.*$", "", a)
    for p, r_ in {r"\br\b": "rue", r"\bav\b": "avenue", r"\bbd\b": "boulevard",
                  r"\bimp\b": "impasse", r"\bpl\b": "place"}.items():
        a = re.sub(p, r_, a)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", a)).strip()


def charger_dvf(dept: str, annee: int, conn) -> int:
    url = f"https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/{dept}.csv.gz"
    log.info("  Téléchargement %s/%s …", dept, annee)
    try:
        r = requests.get(url, timeout=180)
        r.raise_for_status()
    except Exception as e:
        log.warning("  Impossible : %s", e)
        return 0

    # Décompression en mémoire, lecture par chunks
    chunks = []
    with gzip.open(io.BytesIO(r.content), "rt", encoding="utf-8") as f:
        for chunk in pd.read_csv(f, dtype=str, chunksize=50_000, low_memory=False):
            chunk = chunk[chunk["type_local"].isin(TYPES_VALIDES)].copy()
            chunks.append(chunk)

    if not chunks:
        log.warning("  Aucune ligne valide")
        return 0

    df = pd.concat(chunks, ignore_index=True)

    # Numériques
    for col in ["valeur_fonciere", "surface_reelle_bati", "nombre_pieces_principales", "longitude", "latitude"]:
        df[col] = pd.to_numeric(df.get(col, pd.Series(dtype=float)), errors="coerce")

    df["adresse"]            = (df.get("adresse_numero", pd.Series(dtype=str)).fillna("") + " " +
                                df.get("adresse_nom_voie", pd.Series(dtype=str)).fillna("")).str.strip()
    df["adresse_normalisee"] = df["adresse"].apply(normaliser)
    df["prix_m2"]            = (df["valeur_fonciere"] / df["surface_reelle_bati"].replace(0, None)).round(2)
    df["code_commune"]       = df.get("code_commune", pd.Series(dtype=str)).fillna("").str.strip().str.zfill(5)
    df = df.drop_duplicates(subset=["id_mutation"])
    df = df[
        df["valeur_fonciere"].between(1_000, 50_000_000) &
        df["surface_reelle_bati"].between(5, 10_000) &
        df["prix_m2"].between(100, 50_000)
    ].copy()

    # Supprimer les données existantes pour ce dept+année
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM transactions WHERE departement_code=%s AND date_mutation>=%s AND date_mutation<%s",
            (dept, f"{annee}-01-01", f"{annee+1}-01-01"),
        )
    conn.commit()

    # Insertion par batches de 2000
    inserted = 0
    batch = []

    def flush():
        nonlocal inserted
        if not batch:
            return
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO transactions
                   (id_mutation,date_mutation,commune_code,departement_code,
                    adresse,adresse_normalisee,type_local,
                    surface_bati,nb_pieces,valeur_fonciere,prix_m2,
                    latitude,longitude,geom)
                   VALUES %s""",
                batch,
                template="""(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    CASE WHEN %s IS NOT NULL AND %s IS NOT NULL
                         THEN ST_SetSRID(ST_MakePoint(%s,%s),4326) ELSE NULL END)""",
                page_size=1000,
            )
        conn.commit()
        inserted += len(batch)
        batch.clear()

    for _, row in df.iterrows():
        lat = float(row["latitude"])  if pd.notna(row.get("latitude"))  else None
        lng = float(row["longitude"]) if pd.notna(row.get("longitude")) else None
        batch.append((
            row.get("id_mutation"), row.get("date_mutation"),
            row.get("code_commune"), dept,
            row.get("adresse"), row.get("adresse_normalisee"),
            row.get("type_local"),
            float(row["surface_reelle_bati"])        if pd.notna(row.get("surface_reelle_bati")) else None,
            int(row["nombre_pieces_principales"])    if pd.notna(row.get("nombre_pieces_principales")) else None,
            float(row["valeur_fonciere"])            if pd.notna(row.get("valeur_fonciere")) else None,
            float(row["prix_m2"])                   if pd.notna(row.get("prix_m2")) else None,
            lat, lng, lat, lng, lng, lat,
        ))
        if len(batch) >= 2000:
            flush()
    flush()

    log.info("  ✓ %d transactions [%s/%s]", inserted, dept, annee)
    return inserted


def main():
    log.info("DVF — %d depts × %d années", len(DEPARTEMENTS), len(ANNEES))
    conn = get_conn()
    total = 0
    for annee in ANNEES:
        for dept in DEPARTEMENTS:
            try:
                total += charger_dvf(dept, annee, conn)
            except Exception as e:
                log.error("[%s/%s] %s", dept, annee, e)
    conn.close()
    log.info("TOTAL %d transactions", total)


if __name__ == "__main__":
    main()
