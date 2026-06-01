# ImmoBI — Analyse du Marché Immobilier Français
## *Pipeline de données géospatiales · API REST · Interface analytique · Assistant IA*

> **Projet SAE 2026** | Python · PostgreSQL/PostGIS · Flask · Dagster · Azure OpenAI
> Données ouvertes : DVF · ADEME · INSEE · IGN · OSM · DGAC

---

## Table des matières

1. [Vue d ensemble](#vue-densemble)
2. [Architecture](#architecture)
3. [Sources de données](#sources-de-donnees)
4. [Pipeline Dagster](#pipeline-dagster)
5. [Base de données](#base-de-donnees)
6. [API REST](#api-rest)
7. [Frontend](#frontend)
8. [Assistant IA](#assistant-ia--immobi-copilot)
9. [Installation](#installation)
10. [Deploiement](#deploiement)

---

## Vue d'ensemble

**ImmoBI** est un **entrepôt de données immobilières** (*Data Warehouse*) multi-sources centré sur l'analyse spatiale et statistique du marché immobilier français. Il s'inscrit dans une démarche complète d'ingénierie de la donnée (*data engineering*) couvrant :

- **L'extraction** automatisée de 6 sources de données ouvertes hétérogènes (API REST, fichiers Parquet, GeoJSON, CSV compressé gz)
- **La transformation** : normalisation des adresses, détection des valeurs aberrantes, jointure spatiale sous PostGIS en deux passes (adresse exacte + proximité GPS 30m)
- **Le chargement** incrémental et idempotent dans un entrepôt PostgreSQL cloud (Render)
- **L'exposition** via une API REST modulaire et un frontend analytique interactif
- **L'assistance IA** : un copilot conversationnel connecté à la base, capable de générer du SQL à la volée et de répondre en streaming temps réel

L'ensemble du pipeline est **orchestré par Dagster** (*Software-Defined Assets*), garantissant la traçabilité, la reprise sur erreur et la reproductibilité des traitements. Chaque département français constitue une partition indépendante, re-déclenchable à tout moment depuis l'interface Dagster sans impacter les autres données.

---

## Architecture

```
SOURCES DE DONNÉES
DVF · ADEME DPE · INSEE Filosofi · IGN · OSM · DGAC PEB
          |
          v
ORCHESTRATION — Dagster (partitionné par département)
communes -> dvf + dpe + poi --> enrichissement --> quality
            peb + filosofi --/
          |
          v
BASE DE DONNÉES — PostgreSQL 15 + PostGIS 3 (Render)
communes_stats · transactions · dpe · peb_zones · points_interet · quality_log
Vues mat. : prix_m2_par_commune · stats_dpe · stats_peb · stats_distance_gare
          |
          v
API REST — Flask + Gunicorn (Render)
/api/communes · /api/estimateur · /api/carte · /api/analyses
/api/opportunites · /api/transactions · /api/chat
          |
          v
FRONTEND — HTML · CSS · Vanilla JS · Chart.js · Leaflet.js
/ · /commune · /carte · /opportunites · /architecture
```

La page `/architecture` du site documente visuellement l ensemble de la stack.

---

## Sources de données

| Source | Données | Format |
|--------|---------|--------|
| **DVF** data.gouv.fr | Transactions immobilières 2021-2025 | CSV.gz par département/année |
| **ADEME** | Diagnostics de Performance Énergétique (DPE) | API REST paginée |
| **INSEE Filosofi** | Revenus médians et taux de chômage | Parquet via DuckDB |
| **IGN / GeoAPI** | Contours géographiques des communes | GeoJSON |
| **OSM Overpass** | Gares SNCF et établissements scolaires | API Overpass |
| **DGAC PEB** | Zones de bruit aéroport | GeoJSON national |

---

## Pipeline Dagster

### Graphe d assets

```
communes
  |---> dvf    — Transactions DVF 5 ans
  |---> dpe    — Diagnostics ADEME
  `---> poi    — Gares et écoles (OSM)

peb            — Zones bruit national (1 fois)
filosofi       — Revenus/chômage INSEE (1 fois)

enrichissement — Jointures spatiales
quality        — Contrôles qualité horodatés
```

### Enrichissement DVF <-> DPE (2 passes)

| Passe | Technique |
|-------|-----------|
| **1 — Adresse exacte** | commune_code + adresse_normalisee (texte normalisé, sans accents, abréviations développées) |
| **2 — Proximité GPS** | ST_DWithin(t.geom, d.geom, 0.0003) + tri par distance — DPE le plus proche dans ~30m |

### Lancer le pipeline

```bash
dagster dev -m orchestration
# http://localhost:3000 — sélectionner département -> Materialize
```

---

## Base de données

### Tables

| Table | Description | Géométrie |
|-------|-------------|-----------|
| communes_stats | Contours + stats INSEE | MultiPolygon |
| transactions | Ventes DVF enrichies (DPE, distances, PEB) | Point |
| dpe | Diagnostics ADEME avec GPS | Point |
| peb_zones | Polygones de bruit aéroport (zones A-D) | MultiPolygon |
| points_interet | Gares SNCF et écoles | Point |
| quality_log | Traçabilité contrôles qualité | — |

### Vues matérialisées

| Vue | Agrégation |
|-----|-----------|
| prix_m2_par_commune | Médiane, Q25, Q75 par commune × type × année |
| stats_dpe | Prix médian par classe DPE |
| stats_peb | Décote prix par zone PEB |
| stats_distance_gare | Prix médian par tranche distance gare |

```bash
psql  -f sql/schema.sql
```

---

## API REST

Architecture Flask **Blueprints** + Flask-Caching.

| Route | Méthode | Description |
|-------|---------|-------------|
| /api/communes/search | GET | Autocomplétion commune |
| /api/communes/{code}/resume | GET | Fiche synthétique commune |
| /api/estimateur | POST | Estimation prix + score deal |
| /api/carte/prix-m2 | GET | GeoJSON choroplèthe multi-métriques |
| /api/carte/transactions | GET | Transactions géolocalisées |
| /api/analyses/dpe | GET | Prix par classe DPE |
| /api/analyses/transport | GET | Prix par distance gare |
| /api/analyses/bruit | GET | Décote par zone PEB |
| /api/analyses/tendances | GET | Évolution trimestrielle |
| /api/analyses/pois | GET | Gares et écoles d une commune |
| /api/opportunites | GET | Score composite 7 critères |
| /api/transactions | GET | Transactions récentes comparables |
| /api/chat | POST | Assistant IA — streaming SSE |

```bash
flask --app api:create_app run --debug
# http://localhost:5000
```

---

## Frontend

| Page | URL | Librairies |
|------|-----|-----------|
| Analyseur de prix | / | Chart.js |
| Fiche commune | /commune | Chart.js |
| Carte des prix | /carte | Leaflet.js |
| Opportunités | /opportunites | — |
| Architecture | /architecture | — |

---

## Assistant IA — ImmoBI Copilot

Chatbot intégré à toutes les pages (bouton bas droite).

### Pipeline de réponse

```
Question utilisateur
       |
       v
Détection commune -> 1 requête SQL combinée (prix + bruit + DPE)
       |
       v
LLM -> SQL généré --> Exécution PostgreSQL
       ^                  | erreur
       `------------------/ retry automatique (max 3)
                  | succès
                  v
LLM -> Réponse naturelle basée sur données réelles
                  |
                  v
Streaming SSE -> texte affiché mot par mot
```

### Optimisations

- Singleton client AzureOpenAI — instancié une seule fois
- 1 seule requête SQL combinée par commune (vs 3-4 avant)
- Streaming SSE — premier token en < 1s

### Configuration

```env
AZURE_OPENAI_KEY=votre_cle
AZURE_OPENAI_ENDPOINT=https://....openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

---

## Installation

```bash
# 1. Dépendances
pip install -r requirements.txt

# 2. Variables d environnement
cp .env.example .env
# Renseigner DATABASE_URL et clés Azure OpenAI

# 3. Schéma base de données
psql  -f sql/schema.sql

# 4. Pipeline d ingestion (Dagster)
dagster dev -m orchestration

# 5. API Flask
flask --app "api:create_app" run --debug
```

---

## Deploiement

| Composant | Plateforme |
|-----------|-----------|
| API Flask | Render.com (auto-deploy sur push master) |
| Base de données | Render.com PostgreSQL managé + PostGIS |
| Pipeline Dagster | Local (ingestion manuelle) |
| Code source | GitHub branche master |

> Ne jamais commiter .env (présent dans .gitignore). Utiliser les variables Render pour la production.

---

