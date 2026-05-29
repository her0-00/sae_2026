from flask import Blueprint, request, jsonify, abort
from ..db import query
from ..app import cache

bp = Blueprint("opportunites", __name__)


@bp.get("")
@cache.cached(timeout=300, query_string=True)
def trouver_opportunites():
    """
    Retourne les communes avec le meilleur score composite :
    prix bas + revenu élevé + chômage bas + bonne énergie + peu de bruit + gares proches + écoles proches.
    """
    departement = request.args.get("departement")
    type_local = request.args.get("type", "Appartement")
    budget_max = request.args.get("budget_max", type=float)
    surface = request.args.get("surface", 50, type=float)
    dpe_min = request.args.get("dpe_min")
    dist_gare_max = request.args.get("dist_gare_max", type=float)
    dist_ecole_max = request.args.get("dist_ecole_max", type=float)
    chomage_max = request.args.get("chomage_max", type=float)
    bruit_max = request.args.get("bruit_max", type=float)

    if not departement:
        abort(422)

    # Normalise dpe_min pour la comparaison alphabétique SQL (ex: 'D')
    dpe_min_val = dpe_min.strip().upper() if dpe_min else 'G'

    sql = """
        WITH stats_commune AS (
            SELECT
                commune_code,
                AVG(dist_gare_m) as avg_dist_gare,
                AVG(dist_ecole_m) as avg_dist_ecole,
                COALESCE(COUNT(CASE WHEN peb_zone IS NOT NULL THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 0) as pct_bruit,
                COALESCE(COUNT(CASE WHEN dpe_classe <= %s THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN dpe_classe IS NOT NULL THEN 1 END), 0), 100.0) as pct_dpe_ok,
                COALESCE(COUNT(CASE WHEN dpe_classe IN ('A', 'B', 'C', 'D') THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN dpe_classe IS NOT NULL THEN 1 END), 0), 50.0) as pct_dpe_good
            FROM transactions
            WHERE departement_code = %s AND est_valide = TRUE
            GROUP BY commune_code
        ),
        base AS (
            SELECT
                p.commune_code,
                c.nom_commune,
                c.departement_code,
                c.revenu_median,
                c.taux_chomage,
                p.prix_m2_median,
                p.nb_transactions,
                sc.avg_dist_gare,
                sc.avg_dist_ecole,
                sc.pct_bruit,
                sc.pct_dpe_ok,
                sc.pct_dpe_good,
                
                -- score_prix (bas = 100, élevé = 0)
                100 - LEAST(100, GREATEST(0, ROUND(
                    100.0 * p.prix_m2_median / NULLIF(AVG(p.prix_m2_median) OVER (), 0)
                )::int - 50)) AS score_prix,
                
                -- score_revenu (plus élevé = mieux)
                LEAST(100, GREATEST(0, ROUND(
                    100.0 * COALESCE(c.revenu_median, 0) / NULLIF(MAX(c.revenu_median) OVER (), 0)
                )::int)) AS score_revenu,
                
                -- score_chomage (plus bas = mieux)
                100 - LEAST(100, GREATEST(0, ROUND(
                    100.0 * COALESCE(c.taux_chomage, 0) / NULLIF(MAX(c.taux_chomage) OVER (), 0)
                )::int)) AS score_chomage,
                
                -- score_dpe (proportion A-D)
                ROUND(sc.pct_dpe_good)::int AS score_dpe,
                
                -- score_transport (proximité gare, 100 = 0m, 0 = 5000m+)
                LEAST(100, GREATEST(0, ROUND(100.0 * (5000.0 - COALESCE(sc.avg_dist_gare, 3000.0)) / 5000.0)::int)) AS score_transport,
                
                -- score_ecole (proximité école, 100 = 0m, 0 = 2000m+)
                LEAST(100, GREATEST(0, ROUND(100.0 * (2000.0 - COALESCE(sc.avg_dist_ecole, 1000.0)) / 2000.0)::int)) AS score_ecole,
                
                -- score_bruit (100 = pas de bruit, 0 = 50 pourcent de biens affectes)
                LEAST(100, GREATEST(0, ROUND(100.0 - (sc.pct_bruit * 2.0))::int)) AS score_bruit
            FROM prix_m2_par_commune p
            JOIN communes_stats c ON c.commune_code = p.commune_code
            LEFT JOIN stats_commune sc ON sc.commune_code = p.commune_code
            WHERE p.type_local       = %s
              AND c.departement_code = %s
              AND p.annee = (SELECT MAX(annee) FROM prix_m2_par_commune)
              AND p.nb_transactions  >= 5
        )
        SELECT
            commune_code,
            nom_commune,
            departement_code,
            revenu_median,
            taux_chomage,
            prix_m2_median,
            nb_transactions,
            avg_dist_gare,
            avg_dist_ecole,
            pct_bruit,
            pct_dpe_ok,
            score_prix,
            score_revenu,
            score_chomage,
            score_dpe,
            score_transport,
            score_ecole,
            score_bruit,
            ROUND(
                (score_prix * 0.25 + 
                 score_revenu * 0.15 + 
                 score_chomage * 0.15 + 
                 score_dpe * 0.15 + 
                 score_transport * 0.10 + 
                 score_ecole * 0.10 + 
                 score_bruit * 0.10)::NUMERIC, 1
            ) AS score_total
        FROM base
    """

    params = [dpe_min_val, departement, type_local, departement]

    # Filtres dynamiques appliqués sur le select final de base
    where_clauses = []
    if budget_max:
        where_clauses.append("prix_m2_median * %s <= %s")
        params.append(surface)
        params.append(budget_max)
    if dpe_min:
        # Au moins 25% des transactions respectent le DPE min
        where_clauses.append("pct_dpe_ok >= 25.0")
    if dist_gare_max:
        where_clauses.append("avg_dist_gare <= %s")
        params.append(dist_gare_max)
    if dist_ecole_max:
        where_clauses.append("avg_dist_ecole <= %s")
        params.append(dist_ecole_max)
    if chomage_max:
        where_clauses.append("taux_chomage <= %s")
        params.append(chomage_max)
    if bruit_max:
        where_clauses.append("pct_bruit <= %s")
        params.append(bruit_max)

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    sql += " ORDER BY score_total DESC LIMIT 15"

    rows = query(sql, params)
    return jsonify([dict(r) for r in rows])
