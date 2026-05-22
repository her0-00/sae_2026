from flask import Blueprint, request, jsonify, abort
from ..db import query
from ..app import cache

bp = Blueprint("transactions", __name__)


@bp.get("")
@cache.cached(timeout=120, query_string=True)
def liste_transactions():
    commune_code = request.args.get("commune_code")
    type_local = request.args.get("type")
    annee = request.args.get("annee", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)

    if not commune_code:
        abort(422)

    filters = ["commune_code = %s", "est_valide = TRUE"]
    params = [commune_code]

    if type_local:
        filters.append("type_local = %s")
        params.append(type_local)
    if annee:
        filters.append("EXTRACT(YEAR FROM date_mutation) = %s")
        params.append(annee)

    where = "WHERE " + " AND ".join(filters)
    offset = (page - 1) * per_page
    params += [per_page, offset]

    rows = query(
        f"""
        SELECT id, date_mutation, type_local, surface_bati, nb_pieces,
               valeur_fonciere, prix_m2, dpe_classe, peb_zone,
               dist_gare_m, dist_ecole_m, adresse
        FROM transactions
        {where}
        ORDER BY date_mutation DESC
        LIMIT %s OFFSET %s
        """,
        params,
    )
    return jsonify([dict(r) for r in rows])
