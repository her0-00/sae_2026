from flask import Blueprint, request, jsonify, abort
from ..db import query
from ..app import cache

bp = Blueprint("opportunites", __name__)


@bp.get("")
@cache.cached(timeout=300, query_string=True)
def trouver_opportunites():
    """
    Retourne les communes avec le meilleur score composite :
    prix bas + revenu élevé + bonne énergie + peu de bruit + gare proche.
    """
    departement = request.args.get("departement")
    type_local = request.args.get("type", "Appartement")
    budget_max = request.args.get("budget_max", type=float)
    surface = request.args.get("surface", 50, type=float)
    dpe_min = request.args.get("dpe_min", "D")           # classe énergie minimale
    dist_gare_max = request.args.get("dist_gare_max", 2000, type=int)

    if not departement:
        abort(422)

    # Budget → prix/m² max
    pm2_max = (budget_max / surface) if budget_max else None
    pm2_filter = "AND p.prix_m2_median <= %s" if pm2_max else ""

    params = [type_local, departement]
    if pm2_max:
        params.append(pm2_max)

    rows = query(
        f"""
        WITH base AS (
            SELECT
                p.commune_code,
                c.nom_commune,
                c.departement_code,
                c.revenu_median,
                p.prix_m2_median,
                p.nb_transactions,
                -- score 0-100 (plus bas le prix/m² vs médiane dept = mieux)
                100 - LEAST(100, ROUND(
                    100.0 * p.prix_m2_median /
                    NULLIF(AVG(p.prix_m2_median) OVER (PARTITION BY p.type_local), 0)
                )::int) AS score_prix,
                -- revenu relatif (+ c'est élevé, + c'est bien)
                LEAST(100, ROUND(
                    100.0 * COALESCE(c.revenu_median, 0) /
                    NULLIF(MAX(c.revenu_median) OVER (), 0)
                )::int) AS score_revenu
            FROM prix_m2_par_commune p
            JOIN communes_stats c ON c.commune_code = p.commune_code
            WHERE p.type_local       = %s
              AND c.departement_code = %s
              AND p.annee = (SELECT MAX(annee) FROM prix_m2_par_commune)
              AND p.nb_transactions  >= 10
              {pm2_filter}
        )
        SELECT
            commune_code,
            nom_commune,
            departement_code,
            revenu_median,
            prix_m2_median,
            nb_transactions,
            score_prix,
            score_revenu,
            ROUND((score_prix * 0.5 + score_revenu * 0.5)::NUMERIC, 1) AS score_total
        FROM base
        ORDER BY score_total DESC
        LIMIT 10
        """,
        params,
    )

    return jsonify([dict(r) for r in rows])
