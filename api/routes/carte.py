import json
from flask import Blueprint, request, jsonify
from ..db import query
from ..app import cache

bp = Blueprint("carte", __name__)


@bp.get("/prix-m2")
@cache.cached(timeout=600, query_string=True)
def prix_m2_geojson():
    """GeoJSON choroplèthe : communes colorées par prix/m² médian."""
    departement = request.args.get("departement")
    type_local = request.args.get("type", "Appartement")
    annee = request.args.get("annee", type=int)

    if not annee:
        # Dernière année disponible
        row = query("SELECT MAX(annee) AS annee FROM prix_m2_par_commune", fetchone=True)
        annee = row["annee"] if row else 2023

    params = [type_local, annee]
    dept_filter = ""
    if departement:
        dept_filter = "AND c.departement_code = %s"
        params.append(departement)

    rows = query(
        f"""
        SELECT
            c.commune_code,
            c.nom_commune,
            c.departement_code,
            p.prix_m2_median,
            p.nb_transactions,
            ST_Y(ST_Centroid(c.geom)) AS lat,
            ST_X(ST_Centroid(c.geom)) AS lng,
            ST_AsGeoJSON(c.geom)::json AS geometry
        FROM communes_stats c
        JOIN prix_m2_par_commune p
            ON p.commune_code = c.commune_code
           AND p.type_local   = %s
           AND p.annee        = %s
        WHERE c.geom IS NOT NULL
          {dept_filter}
        ORDER BY c.nom_commune
        LIMIT 2000
        """,
        params,
    )

    features = [
        {
            "type": "Feature",
            "geometry": r["geometry"],
            "properties": {
                "commune_code":   r["commune_code"],
                "nom_commune":    r["nom_commune"],
                "departement":    r["departement_code"],
                "prix_m2_median": r["prix_m2_median"],
                "nb_transactions": r["nb_transactions"],
                "lat":            r["lat"],
                "lng":            r["lng"],
            },
        }
        for r in rows
        if r["geometry"]
    ]

    return jsonify({"type": "FeatureCollection", "features": features})


@bp.get("/transactions")
@cache.cached(timeout=120, query_string=True)
def transactions_proches():
    """Transactions dans un rayon autour d'un point (pour marqueurs carte)."""
    try:
        lat = float(request.args["lat"])
        lng = float(request.args["lng"])
        rayon_km = min(float(request.args.get("rayon_km", 5)), 20)
    except (KeyError, ValueError):
        return jsonify({"error": "lat, lng requis"}), 422

    type_local = request.args.get("type")
    params = [lng, lat, rayon_km * 1000]
    type_filter = ""
    if type_local:
        type_filter = "AND type_local = %s"
        params.append(type_local)

    rows = query(
        f"""
        SELECT
            id, date_mutation, type_local, surface_bati, nb_pieces,
            valeur_fonciere, prix_m2, dpe_classe, peb_zone,
            latitude, longitude
        FROM transactions
        WHERE est_valide = TRUE
          AND geom IS NOT NULL
          AND ST_DWithin(geom::geography,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                %s)
          {type_filter}
        ORDER BY date_mutation DESC
        LIMIT 500
        """,
        params,
    )
    return jsonify([dict(r) for r in rows])
