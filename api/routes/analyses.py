from flask import Blueprint, request, jsonify, abort
from ..db import query
from ..app import cache

bp = Blueprint("analyses", __name__)


@bp.get("/dpe")
@cache.cached(timeout=600, query_string=True)
def analyse_dpe():
    commune_code = request.args.get("commune_code")
    type_local = request.args.get("type", "Appartement")
    if not commune_code:
        abort(422)

    rows = query(
        """
        SELECT dpe_classe, nb_transactions, prix_m2_median
        FROM stats_dpe
        WHERE commune_code = %s AND type_local = %s
        ORDER BY dpe_classe
        """,
        (commune_code, type_local),
    )
    return jsonify([dict(r) for r in rows])


@bp.get("/bruit")
@cache.cached(timeout=600, query_string=True)
def analyse_bruit():
    commune_code = request.args.get("commune_code")
    type_local = request.args.get("type", "Appartement")
    if not commune_code:
        abort(422)

    rows = query(
        """
        SELECT peb_zone, peb_aeroport, nb_transactions, prix_m2_median
        FROM stats_peb
        WHERE type_local = %s
          AND (
            peb_aeroport IN (
                SELECT DISTINCT peb_aeroport
                FROM transactions
                WHERE commune_code = %s AND peb_aeroport IS NOT NULL
            )
            OR peb_zone = 'Hors zone'
          )
        ORDER BY peb_zone NULLS LAST
        """,
        (type_local, commune_code),
    )
    return jsonify([dict(r) for r in rows])


@bp.get("/transport")
@cache.cached(timeout=600, query_string=True)
def analyse_transport():
    commune_code = request.args.get("commune_code")
    type_local = request.args.get("type", "Appartement")
    if not commune_code:
        abort(422)

    rows = query(
        """
        SELECT tranche_distance, nb_transactions, prix_m2_median
        FROM stats_distance_gare
        WHERE commune_code = %s AND type_local = %s
        ORDER BY
            CASE tranche_distance
                WHEN '0-500m'   THEN 1
                WHEN '500m-1km' THEN 2
                WHEN '1-2km'    THEN 3
                WHEN '2-5km'    THEN 4
                ELSE 5
            END
        """,
        (commune_code, type_local),
    )
    return jsonify([dict(r) for r in rows])


@bp.get("/tendances")
@cache.cached(timeout=600, query_string=True)
def analyse_tendances():
    commune_code = request.args.get("commune_code")
    type_local = request.args.get("type", "Appartement")
    if not commune_code:
        abort(422)

    rows = query(
        """
        SELECT
            DATE_TRUNC('quarter', date_mutation)::DATE  AS trimestre,
            COUNT(*)                                     AS nb_transactions,
            ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (
                ORDER BY prix_m2)::NUMERIC, 0)          AS prix_m2_median
        FROM transactions
        WHERE commune_code = %s
          AND type_local   = %s
          AND est_valide   = TRUE
          AND date_mutation >= NOW() - INTERVAL '5 years'
        GROUP BY trimestre
        ORDER BY trimestre
        """,
        (commune_code, type_local),
    )
    return jsonify([dict(r) for r in rows])


@bp.get("/ecole")
@cache.cached(timeout=600, query_string=True)
def analyse_ecole():
    commune_code = request.args.get("commune_code")
    type_local = request.args.get("type", "Appartement")
    if not commune_code:
        abort(422)

    rows = query(
        """
        WITH raw_tranches AS (
            SELECT
                CASE
                    WHEN dist_ecole_m <=  500 THEN '0-500m'
                    WHEN dist_ecole_m <= 1000 THEN '500m-1km'
                    WHEN dist_ecole_m <= 2000 THEN '1-2km'
                    WHEN dist_ecole_m <= 5000 THEN '2-5km'
                    ELSE '>5km'
                END AS tranche_distance,
                prix_m2
            FROM transactions
            WHERE commune_code = %s
              AND type_local   = %s
              AND est_valide   = TRUE
              AND dist_ecole_m IS NOT NULL
              AND prix_m2 IS NOT NULL
        )
        SELECT
            tranche_distance,
            COUNT(*) AS nb_transactions,
            ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (
                ORDER BY prix_m2)::NUMERIC, 0) AS prix_m2_median
        FROM raw_tranches
        GROUP BY tranche_distance
        ORDER BY
            CASE tranche_distance
                WHEN '0-500m'   THEN 1
                WHEN '500m-1km' THEN 2
                WHEN '1-2km'    THEN 3
                WHEN '2-5km'    THEN 4
                ELSE 5
            END
        """,
        (commune_code, type_local),
    )
    return jsonify([dict(r) for r in rows])


@bp.get("/pois")
@cache.cached(timeout=600, query_string=True)
def liste_pois():
    commune_code = request.args.get("commune_code")
    if not commune_code:
        abort(422)

    # Types principaux d'équipements (priorité haute, affichés intégralement)
    major_types = ('gare', 'ecole', 'universite', 'cinema', 'salle_sport',
                   'restaurant', 'pharmacie', 'commerce')
    # Types secondaires (affichés en nombre limité pour ne pas noyer la liste)
    minor_types = ('transport', 'parking')

    # Récupérer tous les POI majeurs (sans limite)
    major_rows = query(
        """
        SELECT p.type, p.nom, p.latitude, p.longitude,
               ROUND(ST_Distance(p.geom::geography, ST_Centroid(c.geom)::geography))::integer as dist_centroid_m
        FROM points_interet p
        JOIN communes_stats c ON ST_Within(p.geom, c.geom)
        WHERE c.commune_code = %s
          AND p.type = ANY(%s)
        ORDER BY
            CASE p.type
                WHEN 'gare' THEN 1
                WHEN 'universite' THEN 2
                WHEN 'cinema' THEN 3
                WHEN 'salle_sport' THEN 4
                WHEN 'ecole' THEN 5
                WHEN 'pharmacie' THEN 6
                WHEN 'commerce' THEN 7
                WHEN 'restaurant' THEN 8
            END,
            dist_centroid_m
        LIMIT 150
        """,
        (commune_code, list(major_types)),
    )

    # Récupérer les POI secondaires (top 10 les plus proches du centre, pour info)
    minor_rows = query(
        """
        SELECT p.type, p.nom, p.latitude, p.longitude,
               ROUND(ST_Distance(p.geom::geography, ST_Centroid(c.geom)::geography))::integer as dist_centroid_m
        FROM points_interet p
        JOIN communes_stats c ON ST_Within(p.geom, c.geom)
        WHERE c.commune_code = %s
          AND p.type = ANY(%s)
        ORDER BY dist_centroid_m
        LIMIT 20
        """,
        (commune_code, list(minor_types)),
    )

    all_rows = list(major_rows or []) + list(minor_rows or [])
    return jsonify([dict(r) for r in all_rows])


@bp.get("/ges")
@cache.cached(timeout=600, query_string=True)
def analyse_ges():
    commune_code = request.args.get("commune_code")
    type_local = request.args.get("type", "Appartement")
    if not commune_code:
        abort(422)

    rows = query(
        """
        SELECT
            d.classe_ges,
            COUNT(DISTINCT t.id) as nb_transactions,
            ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2)::NUMERIC, 0) as prix_m2_median
        FROM transactions t
        JOIN dpe d
          ON t.commune_code = d.commune_code
         AND t.adresse_normalisee = d.adresse_normalisee
        WHERE t.commune_code = %s
          AND t.type_local = %s
          AND t.est_valide = TRUE
          AND t.prix_m2 IS NOT NULL
        GROUP BY d.classe_ges
        ORDER BY d.classe_ges
        """,
        (commune_code, type_local),
    )
    return jsonify([dict(r) for r in rows])


@bp.get("/construction")
@cache.cached(timeout=600, query_string=True)
def analyse_construction():
    commune_code = request.args.get("commune_code")
    type_local = request.args.get("type", "Appartement")
    if not commune_code:
        abort(422)

    rows = query(
        """
        SELECT
            CASE
                WHEN d.annee_construction < 1949 THEN 'Avant 1949'
                WHEN d.annee_construction <= 1974 THEN '1949-1974'
                WHEN d.annee_construction <= 1989 THEN '1975-1989'
                WHEN d.annee_construction <= 2000 THEN '1990-2000'
                WHEN d.annee_construction <= 2012 THEN '2001-2012'
                ELSE 'Après 2012'
            END as époque,
            COUNT(DISTINCT t.id) as nb_transactions,
            ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2)::NUMERIC, 0) as prix_m2_median
        FROM transactions t
        JOIN dpe d
          ON t.commune_code = d.commune_code
         AND t.adresse_normalisee = d.adresse_normalisee
        WHERE t.commune_code = %s
          AND t.type_local = %s
          AND t.est_valide = TRUE
          AND t.prix_m2 IS NOT NULL
          AND d.annee_construction IS NOT NULL
        GROUP BY époque
        ORDER BY MIN(d.annee_construction)
        """,
        (commune_code, type_local),
    )
    return jsonify([dict(r) for r in rows])


