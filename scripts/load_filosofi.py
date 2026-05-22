"""
Chargement INSEE Filosofi : revenu médian + taux chômage par commune.
Lance : python scripts/load_filosofi.py
Durée : ~5 min (DuckDB lit uniquement les colonnes utiles du Parquet distant)
"""
import logging, sys
from pathlib import Path
import pandas as pd
import psycopg2.extras
import requests
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts._db import get_conn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("filosofi")

DATASET_ID = "67289477639527408ae687da"
ANNEE      = 2021


def parse_code(x) -> str | None:
    s = str(x).strip()
    if s in ("nan", "", "None"):
        return None
    if any(c.isalpha() for c in s):
        return s.upper().zfill(5)
    try:
        return str(int(float(s))).zfill(5)
    except (ValueError, OverflowError):
        return None


def get_parquet_url() -> str:
    r = requests.get(
        f"https://www.data.gouv.fr/api/1/datasets/{DATASET_ID}/",
        headers={"User-Agent": "Mozilla/5.0"}, timeout=15,
    )
    r.raise_for_status()
    return next(res["url"] for res in r.json()["resources"] if "parquet" in res["title"])


def extraire(parquet_url: str) -> pd.DataFrame:
    import duckdb
    db = duckdb.connect()
    db.execute("INSTALL httpfs; LOAD httpfs;")

    log.info("Extraction revenus médians %d …", ANNEE)
    df_rev = db.execute(f"""
        SELECT code_com, MAX(CAST(valeur AS DOUBLE)) AS revenu_median
        FROM read_parquet('{parquet_url}')
        WHERE source='filosofi_disponible' AND annee={ANNEE} AND clef_json='revenu_median'
        GROUP BY code_com
    """).fetchdf()

    log.info("Extraction taux de chômage %d …", ANNEE)
    df_cho = db.execute(f"""
        SELECT code_com,
            ROUND(
                MAX(CASE WHEN clef_json='chomeurs_15_64_ans_p' THEN CAST(valeur AS DOUBLE) END) /
                NULLIF(MAX(CASE WHEN clef_json='actifs_15_64_ans_c' THEN CAST(valeur AS DOUBLE) END),0)
                * 100, 1
            ) AS taux_chomage
        FROM read_parquet('{parquet_url}')
        WHERE source='rp_actifs_emploi' AND annee={ANNEE}
          AND clef_json IN ('chomeurs_15_64_ans_p','actifs_15_64_ans_c')
        GROUP BY code_com
    """).fetchdf()
    df_cho = df_cho[df_cho["taux_chomage"].between(0, 60)]

    df_rev["commune_code"] = df_rev["code_com"].apply(parse_code)
    df_cho["commune_code"] = df_cho["code_com"].apply(parse_code)

    return (
        df_rev[["commune_code", "revenu_median"]]
        .merge(df_cho[["commune_code", "taux_chomage"]], on="commune_code", how="left")
        .dropna(subset=["commune_code"])
    )


def main():
    log.info("INSEE FILOSOFI %d", ANNEE)
    log.info("Récupération URL Parquet …")
    url = get_parquet_url()
    df = extraire(url)
    log.info("%d communes à mettre à jour", len(df))

    conn = get_conn()
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            UPDATE communes_stats cs SET
                revenu_median = d.revenu_median::numeric,
                taux_chomage  = d.taux_chomage::numeric
            FROM (VALUES %s) AS d(commune_code, revenu_median, taux_chomage)
            WHERE cs.commune_code = d.commune_code
            """,
            [
                (
                    row["commune_code"],
                    str(row["revenu_median"]) if pd.notna(row.get("revenu_median")) else None,
                    str(row["taux_chomage"])  if pd.notna(row.get("taux_chomage"))  else None,
                )
                for _, row in df.iterrows()
            ],
            page_size=2000,
        )
        updated = cur.rowcount
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FILTER (WHERE revenu_median IS NOT NULL) AS rev,
                   COUNT(*) FILTER (WHERE taux_chomage  IS NOT NULL) AS cho,
                   COUNT(*) AS tot
            FROM communes_stats
        """)
        rev, cho, tot = cur.fetchone()
    conn.close()

    log.info("✓ %d communes mises à jour", updated)
    log.info("  revenu_median : %d/%d | taux_chomage : %d/%d", rev, tot, cho, tot)


if __name__ == "__main__":
    main()
