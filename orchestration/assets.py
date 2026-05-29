from dagster import asset, get_dagster_logger, StaticPartitionsDefinition, AssetIn

from scripts import (
    load_communes,
    load_dvf,
    load_dpe,
    load_peb,
    load_poi,
    load_filosofi,
    load_enrichment,
    load_quality,
    config as app_config
)

log = get_dagster_logger()

# Tous les départements français (01 à 95, 2A, 2B, 971 à 976)
tous_les_depts = [f"{i:02d}" for i in range(1, 20)] + ["2A", "2B"] + [f"{i:02d}" for i in range(21, 96)] + ["971", "972", "973", "974", "976"]
departements_partitions = StaticPartitionsDefinition(tous_les_depts)


# ─── ÉTAPE 1 : Communes ────────────────────────────────────────────────────────
@asset(
    group_name="ingestion",
    description="1/4 — Chargement des communes cibles",
    partitions_def=departements_partitions
)
def communes(context):
    dept = context.partition_key
    log.info("Lancement communes pour %s", dept)
    app_config.DEPARTEMENTS = [dept]
    app_config.FORCE_OVERWRITE = True
    load_communes.main()


# ─── ÉTAPE 2 : DVF (attend communes) ──────────────────────────────────────────
@asset(
    group_name="ingestion",
    description="2/4 — Récupération des transactions DVF",
    partitions_def=departements_partitions,
    ins={"_communes": AssetIn("communes")}
)
def dvf(context, _communes):
    dept = context.partition_key
    log.info("Lancement dvf pour %s", dept)
    app_config.DEPARTEMENTS = [dept]
    app_config.FORCE_OVERWRITE = True
    load_dvf.main()


# ─── ÉTAPE 3a : DPE (attend communes, en parallèle avec DVF) ──────────────────
@asset(
    group_name="ingestion",
    description="3/4 — Récupération des DPE",
    partitions_def=departements_partitions,
    ins={"_communes": AssetIn("communes")}
)
def dpe(context, _communes):
    dept = context.partition_key
    log.info("Lancement dpe pour %s", dept)
    app_config.DEPARTEMENTS = [dept]
    app_config.FORCE_OVERWRITE = True
    load_dpe.main()


# ─── ÉTAPE 3b : POI (attend communes, en parallèle avec DVF et DPE) ───────────
@asset(
    group_name="ingestion",
    description="3/4 — Récupération des Gares et Ecoles via OSM",
    partitions_def=departements_partitions,
    ins={"_communes": AssetIn("communes")}
)
def poi(context, _communes):
    dept = context.partition_key
    log.info("Lancement poi pour %s", dept)
    app_config.DEPARTEMENTS = [dept]
    app_config.FORCE_OVERWRITE = True
    load_poi.main()


# ─── ÉTAPE Nationale (sans partition) ─────────────────────────────────────────
@asset(group_name="ingestion", description="Zones de bruit aéroport (National, 1 fois)")
def peb():
    log.info("Lancement peb")
    load_peb.main()


@asset(group_name="ingestion", description="Statistiques INSEE Filosofi (National, 1 fois)")
def filosofi():
    log.info("Lancement filosofi")
    load_filosofi.main()


# ─── ÉTAPE 4 : Enrichissement (à lancer APRÈS les assets d'ingestion) ────────
# Note: dvf/dpe/poi sont partitionnés → Dagster ne permet pas de les déclarer
# comme dépendances formelles d'un asset non-partitionné.
# Lancez enrichissement manuellement APRÈS que dvf/dpe/poi soient terminés.
@asset(
    group_name="enrichment",
    description="4/4 — Croisement spatial et enrichissement de TOUTES les transactions (lancer après ingestion)",
    deps=[peb, filosofi],
)
def enrichissement():
    log.info("Lancement enrichissement")
    load_enrichment.main()


# ─── ÉTAPE 5 : Qualité (attend enrichissement) ────────────────────────────────
@asset(
    deps=[enrichissement],
    group_name="quality",
    description="5/5 — Vérification de la qualité des données"
)
def quality():
    log.info("Lancement quality")
    load_quality.main()
