# SAÉ 2026 — Analyse du Marché Immobilier Français
## *Pipeline de données géospatiales et API d'analyse statistique*

> **Projet universitaire** | Python · PostgreSQL/PostGIS · Flask · Dagster  
> Données ouvertes : DVF (data.gouv.fr) · ADEME · INSEE · IGN · SNCF · OSM

---

## 📋 Table des matières

1. [Vue d'ensemble](#-vue-densemble)
2. [Architecture du système](#-architecture-du-système)
3. [Modèle de données](#-modèle-de-données)
4. [Sources de données](#-sources-de-données)
5. [Pipeline ETL/ELT orchestré](#-pipeline-etlelt-orchestré-avec-dagster)
6. [API REST Backend](#-api-rest-backend-flask)
7. [Frontend Interactif](#-frontend-interactif)
8. [Installation et démarrage](#-installation-et-démarrage)
9. [Métriques de la base de données](#-métriques-de-la-base-de-données)

---

## 🎯 Vue d'ensemble

Ce projet constitue un **entrepôt de données immobilières** (Data Warehouse) multi-sources centré sur l'analyse spatiale et statistique du marché immobilier français. Il s'inscrit dans une démarche complète d'ingénierie de la donnée (*data engineering*) couvrant :

- **L'extraction** automatisée de 6 sources de données ouvertes hétérogènes (API REST, fichiers Parquet, GeoJSON, CSV compressé)
- **La transformation** : normalisation des adresses, détection des valeurs aberrantes, jointure spatiale sous PostGIS
- **Le chargement** incrémental et idempotent dans un entrepôt PostgreSQL cloud (Render)
- **L'exposition** via une API REST documentée et un frontend analytique interactif

L'ensemble du pipeline est **orchestré par Dagster**, un outil de gestion de flux de données de nouvelle génération (*Software-Defined Assets*), garantissant la traçabilité, la reprise sur erreur et la reproductibilité des traitements.

---

## 🏗️ Architecture du système

```
┌─────────────────────────────────────────────────────────────────────┐
│                     SOURCES DE DONNÉES OUVERTES                     │
│  DVF (data.gouv.fr) · ADEME DPE · INSEE Filosofi · IGN · OSM/SNCF · Géorisques │
└─────────────────┬───────────────────────────────────────────────────┘
                  │  HTTP / Parquet / GeoJSON / CSV.gz
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│              ORCHESTRATEUR DAGSTER (Software-Defined Assets)        │
│                                                                     │
│  communes ──► dvf ─────┐                                           │
│           └─► dpe ─────┼──► enrichissement ──► quality             │
│           └─► poi ─────┘         ▲                                  │
│  peb (national) ─────────────────┤                                  │
│  filosofi (national) ─────────────┘                                 │
└─────────────────┬───────────────────────────────────────────────────┘
                  │  psycopg2 / INSERT ... ON CONFLICT
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│           POSTGRESQL 15 + POSTGIS 3 (Cloud — Render)                │
│                                                                     │
│  communes_stats │ transactions │ dpe │ peb_zones │ points_interet   │
│  quality_log    │ prix_m2_par_commune (vue mat.) │ stats_dpe        │
│                 │ stats_peb │ stats_distance_gare (vues mat.)       │
└─────────────────┬───────────────────────────────────────────────────┘
                  │  SQL / psycopg2
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  API REST FLASK (Blueprints)                         │
│  /api/transactions · /api/estimateur · /api/carte · /api/analyses   │
│  /api/opportunites · /api/communes · /api/explorer                  │
└─────────────────┬───────────────────────────────────────────────────┘
                  │  JSON / GeoJSON
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│              FRONTEND (HTML · CSS · JavaScript · Leaflet · Chart.js) │
│  Estimateur · Carte choroplèthe · Analyses · Opportunités · DB Explorer │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Modèle de données

### Schéma relationnel (PostgreSQL + PostGIS)

Le schéma est organisé autour de **6 tables** et **4 vues matérialisées** :

```
communes_stats (PK: commune_code)
       │
       │ FK(commune_code)
       ▼
transactions (PK: id, FK: commune_code)     ◄── données DVF enrichies
  ├─ Géométrie Point (EPSG:4326)
  ├─ dpe_classe / dpe_conso                 ◄── jointure avec table dpe
  ├─ peb_zone / peb_aeroport               ◄── jointure spatiale avec peb_zones
  ├─ dist_gare_m / dist_ecole_m            ◄── calcul avec points_interet
  └─ est_valide / motif_rejet              ◄── contrôle qualité

dpe            — Diagnostics de Performance Énergétique (ADEME)
peb_zones      — Polygones des zones de bruit aéroport (Géorisques)
points_interet — Gares SNCF + Écoles (OSM / data.gouv.fr)
quality_log    — Journal des contrôles qualité horodatés
```

#### Vues matérialisées (performances analytiques)

| Vue | Description | Clé d'agrégation |
|-----|-------------|-----------------|
| `prix_m2_par_commune` | Médiane, moyenne, Q25/Q75 du prix au m² | commune × type_local × année |
| `stats_dpe` | Prix médian par classe énergétique | commune × type_local × classe DPE |
| `stats_peb` | Impact du bruit aérien sur les prix | zone PEB × type_local |
| `stats_distance_gare` | Prix médian par tranche de distance gare | commune × tranche (0-500m, …, >5km) |

> **Choix technique** : Les vues matérialisées (`MATERIALIZED VIEW`) permettent de pré-calculer les agrégats statistiques lourds (médiane avec `PERCENTILE_CONT`, quartiles) et de les exposer via l'API en temps constant, indépendamment du volume de transactions.

#### Index spatiaux et fonctionnels

Tous les attributs géométriques sont indexés via **GIST** (Generalized Search Tree), permettant des jointures spatiales en O(log n) au lieu de O(n²) pour des requêtes de type `ST_Within`, `ST_DWithin` et `ST_Distance`.

---

## 📡 Sources de données

| Source | Données | Format | Volumétrie |
|--------|---------|--------|-----------|
| **DVF** (data.gouv.fr) | Transactions immobilières 2019-2024 | CSV.gz par département/année | ~117k lignes/dépt |
| **ADEME** | Diagnostics de Performance Énergétique (DPE) | API REST paginée | ~216k DPE/dépt |
| **INSEE Filosofi** | Revenus médians + taux de chômage par commune | Fichier Parquet (DuckDB) | 35 000 communes |
| **IGN API Géo** | Contours géographiques des communes | GeoJSON | 36 000 communes |
| **Géorisques** | Zones de Plan d'Exposition au Bruit (PEB) | GeoJSON national | ~150 aéroports |
| **OSM (Overpass)** | Gares SNCF et établissements scolaires | API Overpass + data.gouv.fr | 2 800+ gares |

---

## ⚙️ Pipeline ETL/ELT orchestré avec Dagster

### Concept : Software-Defined Assets

Chaque étape du pipeline est modélisée comme un **Asset Dagster** — un artefact de données versioned dont Dagster suit l'état de matérialisation. Cette approche garantit :
- **Idempotence** : Re-lancer un asset pour un département déjà présent déclenche une confirmation et réinitialise proprement les données concernées.
- **Observabilité** : Chaque run est tracé (durée, logs, statut succès/échec) dans l'interface web Dagster.
- **Partitionnement** : Les assets d'ingestion sont **partitionnés par département** (101 partitions couvrant tous les départements métropolitains et DOM). Il suffit de cliquer sur un département dans l'interface pour lancer son ingestion.

### Graphe de dépendances

```
Phase 1 — INGESTION (par département, sélectionnable dans l'UI)
────────────────────────────────────────────────────────────────
communes
    ├──► dvf   (transactions DVF 5 ans × 1 dépt)
    ├──► dpe   (diagnostics énergétiques)
    └──► poi   (gares SNCF + écoles OSM)

peb        (zones bruit national — 1 seule exécution)
filosofi   (revenus/chômage INSEE — 1 seule exécution)

Phase 2 — ENRICHISSEMENT & QUALITÉ (national, après ingestion)
────────────────────────────────────────────────────────────────
enrichissement  ──► quality
```

### Description des étapes

| Asset | Source | Technique clé | Durée |
|-------|--------|--------------|-------|
| `communes` | API IGN | GeoJSON → `ST_GeomFromGeoJSON`, `ON CONFLICT DO UPDATE` | ~30s |
| `dvf` | data.gouv.fr CSV.gz | Lecture par chunks Pandas, normalisation adresses (Regex), insertion batch `execute_values` | ~5 min |
| `dpe` | API ADEME | Pagination (cursor), déduplication sur `numero_dpe`, jointure BAN | ~3 min |
| `poi` | OSM Overpass + SNCF | Retry sur 3 serveurs Overpass, référentiel SNCF officiel | ~2 min |
| `peb` | Géorisques GeoJSON | Polygones `MultiPolygon` → `ST_GeomFromGeoJSON`, index GIST | ~1 min |
| `filosofi` | INSEE Parquet (DuckDB) | Lecture colonnes distantes via `httpfs`, calcul taux chômage inline, `UPDATE` sélectif | ~5 min |
| `enrichissement` | Base interne | 2 passes DPE (adresse exacte + `ST_DWithin` 30m), `ST_Distance` géographique gares/écoles, `ST_Within` PEB | ~15 min |
| `quality` | Base interne | 9 indicateurs qualité horodatés dans `quality_log` | ~1 min |

---

## 🔌 API REST Backend (Flask)

L'API est construite avec **Flask** selon une architecture modulaire par **Blueprints**. Chaque blueprint gère un domaine métier indépendant.

| Blueprint | Endpoint | Description |
|-----------|----------|-------------|
| `transactions` | `GET /api/transactions` | Lecture paginée des transactions avec filtres multicritères |
| `estimateur` | `GET /api/estimateur` | Estimation de valeur foncière par régression sur les prix voisins |
| `carte` | `GET /api/carte/communes` | GeoJSON enrichi pour carte choroplèthe (centroïde `ST_Centroid` calculé en base) |
| `analyses` | `GET /api/analyses/evolution` | Séries temporelles des prix médians |
| `opportunites` | `GET /api/opportunites` | Scoring multicritère (prix bas × revenus élevés × faible bruit) |
| `communes` | `GET /api/communes/search` | Autocomplétion sur nom ou code INSEE |
| `explorer` | `GET /api/explorer/tables` | Introspection du schéma, pagination données, console SQL sécurisée |

> **Sécurité** : Les endpoints de l'explorateur SQL utilisent `psycopg2.sql.Identifier` pour paramétrer dynamiquement les noms de tables, éliminant tout risque d'injection SQL. Les requêtes libres de la console s'exécutent dans une transaction isolée avec `ROLLBACK` automatique.

---

## 🎨 Frontend Interactif

| Page | Technologie | Fonctionnalité principale |
|------|-------------|--------------------------|
| **Estimateur** | Chart.js | Estimation en temps réel + courbe d'évolution temporelle des prix |
| **Carte des Prix** | Leaflet.js + Esri | Choroplèthe prix/m² · bascule Plan/Satellite · lien Google Maps centroïde |
| **Analyse Commune** | Chart.js | Dossier statistique complet (prix, chômage, revenus, DPE, distances) |
| **Opportunités** | Vanilla JS | Scoring et classement des meilleures affaires selon 5 critères |
| **Explorateur DB** | CodeMirror + AG Grid | Navigation tables · pagination · tri · export CSV · console SQL en temps réel |

---

## 🚀 Installation et démarrage

### Prérequis

- Python 3.12+
- PostgreSQL 15 avec extension PostGIS 3 (ou compte Render gratuit)
- `pip install -r requirements.txt`

### Configuration

```bash
# Copier et renseigner les variables d'environnement
cp .env.example .env
# Éditer DATABASE_URL avec votre chaîne de connexion PostgreSQL
```

### Initialisation du schéma

```bash
psql $DATABASE_URL -f sql/schema.sql
```

### Lancer l'orchestrateur Dagster (pipeline de données)

```bash
dagster dev -m orchestration
# Interface web disponible sur http://127.0.0.1:3000
```

**Dans l'interface Dagster :**
1. Aller dans **Catalog** → Sélectionner les assets d'ingestion
2. Cliquer sur **"Materialize selected"** → Sélectionner le(s) département(s) souhaité(s)
3. Attendre la fin de l'ingestion, puis matérialiser **enrichissement** puis **quality**

### Lancer l'API Flask

```bash
flask --app "api:create_app" run --debug
# API disponible sur http://localhost:5000
```

---

## 📊 Métriques de la base de données

*Données au 23 mai 2026 — Départements 44 (Loire-Atlantique) et 56 (Morbihan)*

| Indicateur | Valeur |
|-----------|--------|
| Transactions totales | **185 742** |
| Transactions géocodées (GPS) | **182 398** (98,2 %) |
| Transactions avec classe DPE | **125 938** (67,8 %) |
| Transactions avec distance gare | **182 398** (98,2 %) |
| Transactions en zone PEB | **5 666** (3,1 %) |
| Diagnostics DPE chargés | **~432 000** |
| Communes couvertes | **456** |
| Communes avec revenu médian INSEE | **456** (100 %) |
| Années couvertes | 2019 → 2024 (5 ans) |
| Gares SNCF référencées | 2 782 (national) |
| Taux de données manquantes GPS | < 2 % (normal : source DVF ancienne) |

> **Note méthodologique** : Les 1,8 % de transactions sans coordonnées GPS correspondent à des actes notariés anciens (antérieurs à 2020) pour lesquels les coordonnées n'étaient pas encore systématiquement renseignées dans la base DVF de la DGFiP. Ces transactions conservent leur valeur foncière et sont incluses dans les statistiques de prix mais sont exclues des analyses spatiales.
