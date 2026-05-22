# ROADMAP — Outil Décisionnel Immobilier (SAE 2026)

> **Objectif** : Construire un outil BI complet permettant de savoir si un bien immobilier est bien ou mal valorisé, selon plusieurs angles : prix, énergie, bruit, transports, contexte socio-économique.

**Stack** : PostgreSQL · Python / Flask · HTML / CSS / JavaScript · Déploiement Render

---

## Vue d'ensemble des phases

```
Phase 0 │ Infrastructure & Setup                   [Semaine 1]
Phase 1 │ Ingestion des données                    [Semaines 2–4]
Phase 2 │ Transformation & Qualité                 [Semaines 5–7]
Phase 3 │ API Flask (backend)                      [Semaines 8–10]
Phase 4 │ Frontend (HTML/CSS/JS)                   [Semaines 11–13]
Phase 5 │ Déploiement Render                       [Semaine 14]
Phase 6 │ Tests, polish & livraison                [Semaines 15–16]
```

---

## Phase 0 — Infrastructure & Setup (Semaine 1)

### Objectif
Mettre en place l'environnement de travail, la base de données, et le squelette du projet avant d'écrire une seule ligne de métier.

### Tâches

#### 0.1 Dépôt & organisation du code
- [ ] Créer la structure de dossiers du projet :
  ```
  /
  ├── ingestion/          # scripts d'import des sources brutes
  ├── transformation/     # scripts de nettoyage et enrichissement
  ├── api/                # application Flask
  │   ├── app.py
  │   ├── routes/
  │   ├── models/
  │   └── utils/
  ├── frontend/           # HTML, CSS, JS
  │   ├── index.html
  │   ├── static/
  │   │   ├── css/
  │   │   └── js/
  │   └── templates/
  ├── sql/                # migrations et scripts SQL
  │   ├── schema.sql      # schéma complet
  │   └── migrations/
  ├── tests/
  ├── .env.example
  ├── requirements.txt
  ├── render.yaml         # config déploiement Render
  └── README.md
  ```
- [ ] Initialiser git, créer `.gitignore` (exclure `.env`, `__pycache__`, les CSV bruts)
- [ ] Créer `requirements.txt` initial :
  - `flask`, `psycopg2-binary`, `sqlalchemy`, `pandas`, `geopandas`, `shapely`
  - `requests`, `python-dotenv`, `flask-cors`

#### 0.2 Base de données PostgreSQL
- [ ] Créer une instance PostgreSQL sur **Render** (Free tier)
- [ ] Activer l'extension **PostGIS** : `CREATE EXTENSION IF NOT EXISTS postgis;`
- [ ] Récupérer la `DATABASE_URL` de connexion Render
- [ ] Créer le fichier `.env` local avec `DATABASE_URL`, `FLASK_ENV=development`
- [ ] Tester la connexion depuis Python (`psycopg2` + `sqlalchemy`)

#### 0.3 Schéma de base de données initial
Créer `sql/schema.sql` avec les tables suivantes :

```sql
-- Transactions immobilières (source DVF)
CREATE TABLE transactions (
    id              BIGSERIAL PRIMARY KEY,
    date_mutation   DATE,
    commune_code    VARCHAR(10),
    adresse         TEXT,
    type_local      VARCHAR(50),        -- 'Appartement', 'Maison', ...
    surface_bati    NUMERIC(10,2),
    nb_pieces       SMALLINT,
    valeur_fonciere NUMERIC(14,2),
    prix_m2         NUMERIC(10,2) GENERATED ALWAYS AS (valeur_fonciere / NULLIF(surface_bati,0)) STORED,
    latitude        NUMERIC(10,6),
    longitude       NUMERIC(10,6),
    geom            GEOMETRY(Point, 4326),
    dpe_classe      CHAR(1),            -- enrichi depuis DPE
    peb_zone        VARCHAR(5),         -- enrichi depuis PEB
    dist_gare_m     INTEGER,            -- enrichi depuis BAN + SNCF
    dist_ecole_m    INTEGER
);

-- Diagnostics de performance énergétique (source DPE)
CREATE TABLE dpe (
    id              BIGSERIAL PRIMARY KEY,
    commune_code    VARCHAR(10),
    adresse         TEXT,
    classe_energie  CHAR(1),
    conso_energie   NUMERIC(10,2),      -- kWh/m²/an
    classe_ges      CHAR(1),
    annee_dpe       SMALLINT
);

-- Données socio-économiques par commune (source INSEE)
CREATE TABLE communes_stats (
    commune_code        VARCHAR(10) PRIMARY KEY,
    nom_commune         TEXT,
    population          INTEGER,
    revenu_median       NUMERIC(10,2),
    taux_chomage        NUMERIC(5,2),
    geom                GEOMETRY(MultiPolygon, 4326)   -- depuis Admin Express
);

-- Zones de bruit (source PEB/DGAC)
CREATE TABLE peb_zones (
    id              BIGSERIAL PRIMARY KEY,
    aeroport        TEXT,
    zone            VARCHAR(5),         -- A, B, C, D
    geom            GEOMETRY(MultiPolygon, 4326)
);

-- Points d'intérêt (gares, écoles)
CREATE TABLE points_interet (
    id              BIGSERIAL PRIMARY KEY,
    type            VARCHAR(20),        -- 'gare', 'ecole'
    nom             TEXT,
    latitude        NUMERIC(10,6),
    longitude       NUMERIC(10,6),
    geom            GEOMETRY(Point, 4326)
);

-- Index spatiaux
CREATE INDEX idx_transactions_geom ON transactions USING GIST(geom);
CREATE INDEX idx_peb_geom ON peb_zones USING GIST(geom);
CREATE INDEX idx_communes_geom ON communes_stats USING GIST(geom);
CREATE INDEX idx_transactions_commune ON transactions(commune_code);
CREATE INDEX idx_transactions_type ON transactions(type_local, date_mutation);
```

---

## Phase 1 — Ingestion des données (Semaines 2–4)

### Objectif
Alimenter les tables `_raw` avec toutes les sources sans transformation. Le principe : charger d'abord, nettoyer ensuite.

### Tâches par source

#### 1.1 DVF — Transactions foncières
- **Source** : [data.gouv.fr/DVF](https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/)
- **Format** : CSV (par département ou national)
- [ ] Télécharger les fichiers CSV (recommandé : 1 à 3 départements pour commencer)
- [ ] Créer `ingestion/ingest_dvf.py` :
  - Lecture chunk par chunk avec `pandas` (`chunksize=50000`) pour gérer le volume
  - Filtres de base : garder seulement `type_local IN ('Appartement','Maison')`
  - Dédoublonnage : une transaction = un `id_mutation` unique (plusieurs parcelles possibles)
  - Insert dans table `transactions_raw` puis `transactions`
- [ ] Valider : compter les lignes insérées, vérifier les nulls sur `valeur_fonciere`

#### 1.2 DPE — Performance énergétique
- **Source** : [data.ademe.fr/DPE v2](https://data.ademe.fr/datasets/dpe-v2-logements-existants)
- **Format** : CSV
- [ ] Télécharger le CSV (filtrer sur les départements retenus)
- [ ] Créer `ingestion/ingest_dpe.py` :
  - Normaliser l'adresse (minuscules, suppression accents, abréviations)
  - Insert dans table `dpe`
- [ ] Valider : distribution des classes énergie (A–G)

#### 1.3 BAN — Géocodage des adresses
- **Source** : [adresse.data.gouv.fr](https://adresse.data.gouv.fr/data/ban/adresses/latest/)
- **Format** : CSV (lat/lng par adresse)
- **Rôle** : Enrichir DVF avec des coordonnées GPS (indispensable pour les jointures spatiales)
- [ ] Option A (fichier local) : télécharger le CSV BAN pour les départements cibles
- [ ] Option B (API) : appeler `https://api-adresse.data.gouv.fr/search/?q=<adresse>` pour chaque ligne DVF non géocodée (respecter le rate limit)
- [ ] Créer `ingestion/geocode_transactions.py` :
  - Normaliser l'adresse DVF avant la requête BAN
  - Stocker lat/lng dans `transactions.latitude`, `transactions.longitude`
  - Mettre à jour `geom` : `ST_SetSRID(ST_MakePoint(lng, lat), 4326)`

#### 1.4 PEB — Zones de bruit
- **Source** : [GéoRisques API](https://georisques.gouv.fr) + [data.gouv.fr DGAC](https://www.data.gouv.fr/fr/datasets/?q=plan+exposition+bruit)
- **Format** : GeoJSON / Shapefile
- [ ] Télécharger les polygones PEB pour les aéroports proches des départements cibles
- [ ] Créer `ingestion/ingest_peb.py` :
  - Lire le GeoJSON avec `geopandas`
  - Reprojeter en WGS84 si nécessaire
  - Insert dans `peb_zones` avec `ST_GeomFromText` ou `geopandas.to_postgis`

#### 1.5 INSEE — Données socio-économiques
- **Source** : [insee.fr](https://www.insee.fr/fr/statistiques)
  - Revenus par commune : [Filosofi](https://www.insee.fr/fr/statistiques/6692392)
  - Chômage : [Taux de chômage localisés](https://www.insee.fr/fr/statistiques/6452724)
- **Format** : CSV / Excel
- [ ] Télécharger les fichiers pour les communes concernées
- [ ] Créer `ingestion/ingest_insee.py` :
  - Lire avec `pandas`, normaliser le code commune (5 chiffres, zéro de tête)
  - Insert dans `communes_stats`

#### 1.6 Admin Express — Contours communes
- **Source** : [IGN Admin Express](https://www.data.gouv.fr/fr/datasets/adminexpress/)
- **Format** : GeoJSON / Shapefile
- [ ] Télécharger les polygones de communes
- [ ] Créer `ingestion/ingest_admin.py` :
  - Lire avec `geopandas`, filtrer sur les départements cibles
  - Insert dans `communes_stats.geom`

#### 1.7 Points d'intérêt — Gares & Écoles
- **Gares SNCF** : [data.sncf.com](https://data.sncf.com/) (liste des gares avec coordonnées)
- **Écoles** : [Overpass API](https://overpass-turbo.dev/) (requête OpenStreetMap)
- [ ] Créer `ingestion/ingest_poi.py` :
  - Télécharger les gares SNCF (JSON ou CSV)
  - Requêter Overpass API pour les écoles dans la bounding box des départements
  - Insert dans `points_interet`

---

## Phase 2 — Transformation & Qualité des données (Semaines 5–7)

### Objectif
Passer des données brutes à des données analytiques fiables. Chaque règle de filtrage doit être documentée.

### Tâches

#### 2.1 Nettoyage DVF
- [ ] Créer `transformation/clean_transactions.py` :
  - **Dédoublonnage** : garder une ligne par `id_mutation` (agréger les parcelles)
  - **Filtres outliers** (à documenter) :
    - Supprimer `valeur_fonciere < 1000` (cession familiale symbolique)
    - Supprimer `prix_m2 < 100` ou `prix_m2 > 50000` (valeurs aberrantes)
    - Supprimer `surface_bati < 5` m²
  - **Valider les nulls** : loguer les transactions sans adresse, sans surface
  - Créer une table `transactions_rejetees` avec motif pour auditabilité

#### 2.2 Jointure DVF ↔ DPE (enrichissement énergie)
- [ ] Créer `transformation/enrich_dpe.py` :
  - Normaliser les adresses des deux tables (même fonction de nettoyage)
  - Jointure sur `adresse_normalisee + commune_code`
  - Taux de match attendu : 30–50 % (acceptable, DPE ne couvre pas tout)
  - Mettre à jour `transactions.dpe_classe`

#### 2.3 Jointure spatiale DVF ↔ PEB (zones de bruit)
- [ ] Créer `transformation/enrich_peb.py` :
  ```sql
  UPDATE transactions t
  SET peb_zone = p.zone
  FROM peb_zones p
  WHERE ST_Within(t.geom, p.geom);
  ```
  - Mettre à jour `transactions.peb_zone`

#### 2.4 Calcul des distances (gares, écoles)
- [ ] Créer `transformation/enrich_distances.py` :
  ```sql
  -- Distance à la gare la plus proche
  UPDATE transactions t
  SET dist_gare_m = (
      SELECT ST_Distance(t.geom::geography, p.geom::geography)::integer
      FROM points_interet p
      WHERE p.type = 'gare'
      ORDER BY t.geom <-> p.geom
      LIMIT 1
  );
  ```
  - Répéter pour `dist_ecole_m`

#### 2.5 Agrégations analytiques
- [ ] Créer des **vues matérialisées** pour les requêtes fréquentes :
  ```sql
  CREATE MATERIALIZED VIEW prix_m2_par_commune AS
  SELECT
      commune_code,
      type_local,
      EXTRACT(YEAR FROM date_mutation) AS annee,
      COUNT(*)                          AS nb_transactions,
      PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS prix_m2_median,
      AVG(prix_m2)                      AS prix_m2_moyen
  FROM transactions
  WHERE prix_m2 IS NOT NULL
  GROUP BY commune_code, type_local, annee;
  ```
  - Vue : `stats_dpe` (prix_m2 médian par classe énergie)
  - Vue : `stats_peb` (prix_m2 médian par zone bruit)
  - Vue : `stats_distance_gare` (prix_m2 par tranche de distance)

#### 2.6 Checks qualité automatisés
- [ ] Créer `transformation/quality_checks.py` :
  - % de transactions géocodées (objectif > 80 %)
  - % de transactions avec DPE (objectif > 30 %)
  - Unicité `id_mutation` dans `transactions`
  - Pas de `prix_m2 < 0`
  - Loguer les résultats dans une table `quality_log(run_at, check_name, passed, details)`

---

## Phase 3 — API Flask (Backend) (Semaines 8–10)

### Objectif
Exposer les données sous forme d'API REST consommable par le frontend.

### Architecture Flask

```
api/
├── app.py              # factory pattern (create_app)
├── config.py           # config depuis .env
├── db.py               # connexion SQLAlchemy
├── routes/
│   ├── transactions.py
│   ├── estimateur.py
│   ├── carte.py
│   ├── analyses.py
│   └── opportunites.py
└── utils/
    └── filters.py
```

### Endpoints à implémenter

#### 3.1 Données de carte
```
GET /api/carte/prix-m2
  ?departement=75&type=Appartement&annee=2023
  → GeoJSON: communes avec prix_m2_median (pour choroplèthe)

GET /api/carte/transactions
  ?lat=48.85&lng=2.35&rayon_km=5&type=Maison
  → Liste des transactions proches (max 500)
```

#### 3.2 Estimateur de prix
```
POST /api/estimateur
  body: { commune_code, surface, nb_pieces, type_local, annee? }
  → {
      prix_estime: 350000,
      fourchette_basse: 320000,
      fourchette_haute: 380000,
      prix_m2_median_commune: 4200,
      nb_comparables: 87,
      score_deal: "bon" | "correct" | "cher"
    }
```
- Logique : comparer le prix_m2 saisi aux percentiles 25/50/75 de la commune + type

#### 3.3 Analyses thématiques
```
GET /api/analyses/dpe?commune_code=75056
  → prix_m2_median par classe A–G, pour cette commune

GET /api/analyses/bruit?commune_code=75056
  → prix_m2_median par zone PEB vs hors zone

GET /api/analyses/transport?commune_code=75056
  → prix_m2 moyen par tranche de distance (0–500m, 500–1km, 1–2km, >2km)

GET /api/analyses/tendances?commune_code=75056&type=Appartement
  → volume et prix médian par trimestre, 5 dernières années
```

#### 3.4 Finder d'opportunités
```
GET /api/opportunites
  ?departement=69&type=Appartement&budget_max=200000
  → Top 10 communes par score composite :
    score = f(prix_m2_sous_médiane, revenu_élevé, bonne_DPE, hors_PEB, proche_gare)
```

#### 3.5 Recherche de commune
```
GET /api/communes/search?q=Lyon
  → [{ code, nom, departement }]

GET /api/communes/{code}/resume
  → { prix_m2_median, revenu_median, taux_chomage, nb_transactions_12m }
```

### 3.6 Configuration Flask
- [ ] Connexion PostgreSQL via `psycopg2` + `SQLAlchemy`
- [ ] CORS activé (`flask-cors`) pour que le frontend puisse appeler l'API
- [ ] Gestion des erreurs (`404`, `422`, `500`) avec réponse JSON structurée
- [ ] Variables d'environnement via `python-dotenv`
- [ ] `Procfile` pour Render : `web: gunicorn api.app:app`

---

## Phase 4 — Frontend HTML/CSS/JavaScript (Semaines 11–13)

### Objectif
Interface simple, efficace, lisible — sans framework JS lourd. Vanilla JS + quelques librairies légères.

### Librairies frontend retenues
- **Leaflet.js** : carte interactive (choroplèthe + marqueurs transactions)
- **Chart.js** : graphiques (tendances, DPE, bruit, transport)
- **Choices.js** (optionnel) : select avec recherche pour les communes
- Pas de framework (React/Vue/Angular) : HTML/CSS/JS natif suffit

### Pages et vues

#### 4.1 Page d'accueil / Estimateur (`index.html`)
```
┌─────────────────────────────────────────────────────────────┐
│  🏠  Est-ce un bon prix ?                                   │
│                                                              │
│  Commune : [____________________]   Type : [Appartement ▼] │
│  Surface : [___] m²   Pièces : [___]   Prix demandé : [___] │
│                           [Analyser →]                       │
├─────────────────────────────────────────────────────────────┤
│  RÉSULTAT                                                   │
│  ┌──────────┐  Prix estimé : 320 000 – 380 000 €           │
│  │ ✅ BON   │  Prix/m² : 4 200 €/m²  (médiane commune)     │
│  │  DEAL    │  87 biens comparables sur 12 mois            │
│  └──────────┘                                               │
└─────────────────────────────────────────────────────────────┘
```

#### 4.2 Carte des prix (`carte.html`)
- Carte Leaflet centrée sur la France
- Choroplèthe : communes colorées par prix/m² médian
- Filtres : type de bien, année, département
- Clic sur commune → popover avec stats clés + lien vers fiche commune

#### 4.3 Fiche commune (`commune.html?code=75056`)
- Résumé : prix médian, nb transactions, revenu médian, taux chômage
- 4 graphiques Chart.js :
  1. Tendance prix/m² (courbe temporelle)
  2. Impact DPE (barres A–G)
  3. Impact bruit (comparaison PEB vs hors zone)
  4. Prime de transport (courbe distance vs prix)

#### 4.4 Finder d'opportunités (`opportunites.html`)
- Formulaire : département, type de bien, budget max, critères (DPE min, distance gare max)
- Résultat : tableau des 10 meilleures communes avec score et détails

### 4.5 Design & CSS
- [ ] CSS Variables pour la charte couleur
- [ ] Responsive (mobile-first, breakpoint 768px)
- [ ] Score visuel : badge coloré vert/orange/rouge selon `score_deal`
- [ ] Loading spinner pendant les appels API
- [ ] Gestion des erreurs côté UI (commune introuvable, pas de données)

---

## Phase 5 — Déploiement Render (Semaine 14)

### Objectif
Mettre en production sur Render avec la base PostgreSQL hébergée là aussi.

### Configuration `render.yaml`

```yaml
services:
  - type: web
    name: sae-2026-api
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "gunicorn api.app:app"
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: sae-2026-db
          property: connectionString
      - key: FLASK_ENV
        value: production

databases:
  - name: sae-2026-db
    plan: free
    databaseName: sae2026
    postgresMajorVersion: 16
```

### Tâches déploiement
- [ ] Pousser le code sur GitHub (repo public ou privé)
- [ ] Connecter le repo à Render (auto-deploy sur push `main`)
- [ ] Créer la base PostgreSQL sur Render → récupérer `DATABASE_URL`
- [ ] Ajouter `DATABASE_URL` en variable d'environnement dans Render
- [ ] Lancer `sql/schema.sql` sur la base Render (via `psql` ou l'interface Render)
- [ ] Lancer les scripts d'ingestion depuis la machine locale (connexion directe à la DB Render)
- [ ] Vérifier que les endpoints API répondent sur l'URL Render
- [ ] Servir le frontend : option A (Flask sert les fichiers statiques), option B (Render Static Site séparé)

> **Note Render Free Tier** : la base s'endort après 90 jours d'inactivité. Les instances web s'endorment après 15 min. Prévoir un endpoint `/health` pour le keep-alive.

---

## Phase 6 — Tests, Polish & Livraison (Semaines 15–16)

### Tests
- [ ] Tests unitaires (`pytest`) sur les fonctions de nettoyage et calcul de score
- [ ] Tests d'intégration sur les endpoints Flask principaux (avec `pytest-flask`)
- [ ] Vérification manuelle des parcours utilisateurs clés :
  - Estimer le prix d'un bien connu
  - Visualiser la carte d'un département
  - Trouver les meilleures communes dans un budget

### Polish
- [ ] Optimiser les requêtes lentes (EXPLAIN ANALYZE, index manquants)
- [ ] Rafraîchir les vues matérialisées : `REFRESH MATERIALIZED VIEW CONCURRENTLY`
- [ ] Ajouter un cache simple côté Flask pour les réponses géo lourdes (`flask-caching`)
- [ ] Documenter l'API (commentaires dans le code ou Swagger/OpenAPI simple)
- [ ] Rédiger le README final avec les choix techniques et les résultats

### Livraison
- [ ] URL publique fonctionnelle sur Render
- [ ] Tous les scripts d'ingestion documentés et reproductibles
- [ ] Rapport des checks qualité (taux de géocodage, taux de match DPE, etc.)
- [ ] Démonstration des 4 angles d'analyse : prix, énergie, bruit, transport

---

## Résumé des dépendances entre phases

```
Phase 0 (infra)
    │
    ▼
Phase 1 (ingestion)
    │
    ├── 1.1 DVF ──────────────────────────────────────┐
    ├── 1.3 BAN (géocodage DVF) ────────────────────┐ │
    │                                               │ │
    ▼                                               ▼ ▼
Phase 2 (transformation)
    │  2.1 nettoyage DVF
    │  2.2 enrichissement DPE     ← 1.2 DPE
    │  2.3 enrichissement PEB     ← 1.4 PEB
    │  2.4 calcul distances       ← 1.7 POI
    │  2.5 vues matérialisées
    │
    ▼
Phase 3 (API Flask)     Phase 4 (Frontend)
    │                       │
    └───────────────────────┘
                │
                ▼
         Phase 5 (Render)
                │
                ▼
         Phase 6 (Tests & livraison)
```

---

## KPIs de réussite du projet

| Indicateur | Objectif minimum |
|---|---|
| Transactions ingérées | > 100 000 |
| Taux de géocodage (DVF → BAN) | > 80 % |
| Taux de match DPE | > 30 % |
| Temps de réponse API estimateur | < 500 ms |
| Couverture des communes | tous les départements sélectionnés |
| Disponibilité Render | > 95 % |

---

## Sources officielles de référence

| Donnée | URL |
|---|---|
| DVF transactions | https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/ |
| DPE logements existants | https://data.ademe.fr/datasets/dpe-v2-logements-existants |
| GéoRisques API (PEB) | https://georisques.gouv.fr/api/v1/ |
| PEB polygones DGAC | https://www.data.gouv.fr/fr/datasets/?q=plan+exposition+bruit |
| INSEE Filosofi (revenus) | https://www.insee.fr/fr/statistiques/6692392 |
| BAN géocodage | https://adresse.data.gouv.fr/data/ban/adresses/latest/ |
| API géocodage BAN | https://api-adresse.data.gouv.fr/search/ |
| IGN Admin Express | https://www.data.gouv.fr/fr/datasets/adminexpress/ |
| SNCF gares | https://data.sncf.com/explore/dataset/liste-des-gares/ |
| Overpass API (OSM) | https://overpass-turbo.eu/ |
| PostGIS docs | https://postgis.net/documentation/ |
| Render docs | https://render.com/docs |
