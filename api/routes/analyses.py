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
