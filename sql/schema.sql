-- =============================================================
--  SAE 2026 — Schéma PostgreSQL + PostGIS
--  Lancer : psql $DATABASE_URL -f sql/schema.sql
-- =============================================================

-- Extension spatiale (obligatoire avant toute colonne GEOMETRY)
CREATE EXTENSION IF NOT EXISTS postgis;

-- =============================================================
--  1. COMMUNES — contours + stats INSEE
-- =============================================================
CREATE TABLE IF NOT EXISTS communes_stats (
    commune_code        VARCHAR(10) PRIMARY KEY,
    nom_commune         TEXT        NOT NULL,
    departement_code    VARCHAR(5),
    region_code         VARCHAR(5),
    population          INTEGER,
    revenu_median       NUMERIC(10,2),   -- €/an (source INSEE Filosofi)
    taux_chomage        NUMERIC(5,2),    -- % (source INSEE)
    geom                GEOMETRY(MultiPolygon, 4326)
);

CREATE INDEX IF NOT EXISTS idx_communes_geom
    ON communes_stats USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_communes_dept
    ON communes_stats(departement_code);

-- =============================================================
--  2. TRANSACTIONS — source DVF enrichie
-- =============================================================
CREATE TABLE IF NOT EXISTS transactions (
    id                  BIGSERIAL PRIMARY KEY,
    id_mutation         VARCHAR(50),             -- identifiant DVF unique
    date_mutation       DATE,
    commune_code        VARCHAR(10) REFERENCES communes_stats(commune_code),
    departement_code    VARCHAR(5),
    adresse             TEXT,
    adresse_normalisee  TEXT,                    -- adresse nettoyée pour jointure BAN
    type_local          VARCHAR(50),             -- 'Appartement', 'Maison', 'Local industriel'...
    surface_bati        NUMERIC(10,2),           -- m²
    nb_pieces           SMALLINT,
    valeur_fonciere     NUMERIC(14,2),           -- €
    prix_m2             NUMERIC(10,2),           -- calculé à l'ingestion
    latitude            NUMERIC(10,6),
    longitude           NUMERIC(10,6),
    geom                GEOMETRY(Point, 4326),
    -- champs enrichis (remplis lors de la phase de transformation)
    dpe_classe          CHAR(1),                 -- A B C D E F G (source DPE)
    dpe_conso           NUMERIC(8,2),            -- kWh/m²/an
    peb_zone            VARCHAR(5),              -- A B C D ou NULL (source PEB)
    peb_aeroport        TEXT,
    dist_gare_m         INTEGER,                 -- mètres vers gare la plus proche
    dist_ecole_m        INTEGER,                 -- mètres vers école la plus proche
    -- contrôle qualité
    est_valide          BOOLEAN DEFAULT TRUE,
    motif_rejet         TEXT
);

CREATE INDEX IF NOT EXISTS idx_transactions_geom
    ON transactions USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_transactions_commune
    ON transactions(commune_code);
CREATE INDEX IF NOT EXISTS idx_transactions_type_date
    ON transactions(type_local, date_mutation);
CREATE INDEX IF NOT EXISTS idx_transactions_mutation
    ON transactions(id_mutation);
CREATE INDEX IF NOT EXISTS idx_transactions_dept
    ON transactions(departement_code);

-- =============================================================
--  3. DPE — Diagnostics de performance énergétique
-- =============================================================
CREATE TABLE IF NOT EXISTS dpe (
    id                  BIGSERIAL PRIMARY KEY,
    numero_dpe          VARCHAR(50),
    commune_code        VARCHAR(10),
    adresse             TEXT,
    adresse_normalisee  TEXT,
    classe_energie      CHAR(1),                 -- A à G
    conso_energie       NUMERIC(10,2),           -- kWh/m²/an (ep)
    classe_ges          CHAR(1),                 -- A à G
    type_batiment       VARCHAR(50),
    annee_construction  SMALLINT,
    annee_dpe           SMALLINT
);

CREATE INDEX IF NOT EXISTS idx_dpe_commune
    ON dpe(commune_code);
CREATE INDEX IF NOT EXISTS idx_dpe_adresse
    ON dpe(adresse_normalisee);

-- =============================================================
--  4. PEB — Zones de bruit aéroport (polygones)
-- =============================================================
CREATE TABLE IF NOT EXISTS peb_zones (
    id                  BIGSERIAL PRIMARY KEY,
    aeroport            TEXT        NOT NULL,
    code_icao           VARCHAR(10),
    zone                VARCHAR(5)  NOT NULL,    -- A (+ fort) → D (+ faible)
    geom                GEOMETRY(MultiPolygon, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_peb_geom
    ON peb_zones USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_peb_aeroport
    ON peb_zones(aeroport);

-- =============================================================
--  5. POINTS D'INTÉRÊT — gares SNCF et écoles
-- =============================================================
CREATE TABLE IF NOT EXISTS points_interet (
    id                  BIGSERIAL PRIMARY KEY,
    type                VARCHAR(20) NOT NULL,    -- 'gare' | 'ecole'
    nom                 TEXT,
    commune_code        VARCHAR(10),
    latitude            NUMERIC(10,6),
    longitude           NUMERIC(10,6),
    geom                GEOMETRY(Point, 4326)
);

CREATE INDEX IF NOT EXISTS idx_poi_geom
    ON points_interet USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_poi_type
    ON points_interet(type);

-- =============================================================
--  6. QUALITY LOG — traçabilité des checks
-- =============================================================
CREATE TABLE IF NOT EXISTS quality_log (
    id          BIGSERIAL PRIMARY KEY,
    run_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    check_name  TEXT        NOT NULL,
    passed      BOOLEAN     NOT NULL,
    value       NUMERIC,                         -- valeur mesurée (ex: taux de géocodage)
    details     TEXT
);

-- =============================================================
--  7. VUES MATÉRIALISÉES analytiques
--     (à rafraîchir après chaque ingestion/transformation)
-- =============================================================

-- Prix médian par commune / type / année
CREATE MATERIALIZED VIEW IF NOT EXISTS prix_m2_par_commune AS
SELECT
    t.commune_code,
    c.nom_commune,
    c.departement_code,
    t.type_local,
    EXTRACT(YEAR FROM t.date_mutation)::SMALLINT      AS annee,
    COUNT(*)                                           AS nb_transactions,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (
        ORDER BY t.prix_m2)::NUMERIC, 0)              AS prix_m2_median,
    ROUND(AVG(t.prix_m2)::NUMERIC, 0)                 AS prix_m2_moyen,
    ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (
        ORDER BY t.prix_m2)::NUMERIC, 0)              AS prix_m2_q25,
    ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (
        ORDER BY t.prix_m2)::NUMERIC, 0)              AS prix_m2_q75
FROM transactions t
LEFT JOIN communes_stats c ON t.commune_code = c.commune_code
WHERE t.est_valide = TRUE
  AND t.prix_m2 IS NOT NULL
GROUP BY t.commune_code, c.nom_commune, c.departement_code, t.type_local, annee;

CREATE UNIQUE INDEX IF NOT EXISTS idx_prix_commune_uniq
    ON prix_m2_par_commune(commune_code, type_local, annee);

-- Prix médian par classe DPE
CREATE MATERIALIZED VIEW IF NOT EXISTS stats_dpe AS
SELECT
    commune_code,
    type_local,
    dpe_classe,
    COUNT(*)                                           AS nb_transactions,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (
        ORDER BY prix_m2)::NUMERIC, 0)                AS prix_m2_median
FROM transactions
WHERE est_valide = TRUE
  AND dpe_classe IS NOT NULL
  AND prix_m2 IS NOT NULL
GROUP BY commune_code, type_local, dpe_classe;

-- Prix médian par zone PEB
CREATE MATERIALIZED VIEW IF NOT EXISTS stats_peb AS
SELECT
    COALESCE(peb_zone, 'Hors zone')                   AS peb_zone,
    peb_aeroport,
    type_local,
    COUNT(*)                                           AS nb_transactions,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (
        ORDER BY prix_m2)::NUMERIC, 0)                AS prix_m2_median
FROM transactions
WHERE est_valide = TRUE
  AND prix_m2 IS NOT NULL
GROUP BY peb_zone, peb_aeroport, type_local;

-- Prix médian par tranche de distance à la gare
CREATE MATERIALIZED VIEW IF NOT EXISTS stats_distance_gare AS
SELECT
    commune_code,
    type_local,
    CASE
        WHEN dist_gare_m <=  500 THEN '0-500m'
        WHEN dist_gare_m <= 1000 THEN '500m-1km'
        WHEN dist_gare_m <= 2000 THEN '1-2km'
        WHEN dist_gare_m <= 5000 THEN '2-5km'
        ELSE '>5km'
    END                                                AS tranche_distance,
    COUNT(*)                                           AS nb_transactions,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (
        ORDER BY prix_m2)::NUMERIC, 0)                AS prix_m2_median
FROM transactions
WHERE est_valide = TRUE
  AND dist_gare_m IS NOT NULL
  AND prix_m2 IS NOT NULL
GROUP BY commune_code, type_local, tranche_distance;
