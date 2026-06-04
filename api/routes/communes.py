from flask import Blueprint, request, jsonify, abort
from ..db import query
from ..app import cache

bp = Blueprint("communes", __name__)


@bp.get("/search")
@cache.cached(timeout=600, query_string=True)
def search_communes():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])

    rows = query(
        """
        SELECT commune_code, nom_commune, departement_code
        FROM communes_stats
        WHERE nom_commune ILIKE %s
        ORDER BY nom_commune
        LIMIT 20
        """,
        (f"%{q}%",),
    )
    return jsonify([dict(r) for r in rows])


@bp.get("/<code>/resume")
@cache.cached(timeout=300)
def resume_commune(code):
    row = query(
        """
        SELECT
            c.commune_code,
            c.nom_commune,
            c.departement_code,
            c.population,
            c.revenu_median,
            c.taux_chomage,
            p.prix_m2_median,
            p.nb_transactions,
            p.type_local,
            p.annee,
            l.loyer_m2_appartement,
            l.loyer_m2_maison
        FROM communes_stats c
        LEFT JOIN prix_m2_par_commune p
            ON p.commune_code = c.commune_code
           AND p.annee = EXTRACT(YEAR FROM NOW()) - 1
           AND p.type_local = 'Appartement'
        LEFT JOIN communes_loyers l
            ON l.commune_code = c.commune_code
        WHERE c.commune_code = %s
        LIMIT 1
        """,
        (code,),
        fetchone=True,
    )
    if not row:
        abort(404)
    return jsonify(dict(row))
