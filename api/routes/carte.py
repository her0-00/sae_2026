import json
from flask import Blueprint, request, jsonify
from ..db import query
from ..app import cache

bp = Blueprint("carte", __name__)


@bp.get("/prix-m2")
@cache.cached(timeout=600, query_string=True)
def prix_m2_geojson():
    """GeoJSON choroplèthe : communes colorées par prix/m² médian ou autre métrique."""
    departement = request.args.get("departement")
    type_local = request.args.get("type", "Appartement")
    annee = request.args.get("annee", type=int)
    metric = request.args.get("metric", "prix")

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
            c.revenu_median,
            c.taux_chomage,
            p.prix_m2_median,
            p.nb_transactions,
            dpe_stats.avg_dpe,
            bruit_stats.pct_bruit,
            dpe_ges_stats.avg_ges,
            dpe_ges_stats.avg_annee,
            ST_Y(ST_Centroid(c.geom)) AS lat,
            ST_X(ST_Centroid(c.geom)) AS lng,
            ST_AsGeoJSON(c.geom)::json AS geometry
        FROM communes_stats c
        JOIN prix_m2_par_commune p
            ON p.commune_code = c.commune_code
           AND p.type_local   = %s
           AND p.annee        = %s
        LEFT JOIN (
            SELECT 
                commune_code,
                ROUND(AVG(
                    CASE dpe_classe
                        WHEN 'A' THEN 1.0
                        WHEN 'B' THEN 2.0
                        WHEN 'C' THEN 3.0
                        WHEN 'D' THEN 4.0
                        WHEN 'E' THEN 5.0
                        WHEN 'F' THEN 6.0
                        WHEN 'G' THEN 7.0
                    END
                )::numeric, 1) as avg_dpe
            FROM transactions
            WHERE est_valide = TRUE AND dpe_classe IS NOT NULL
            GROUP BY commune_code
        ) dpe_stats ON dpe_stats.commune_code = c.commune_code
        LEFT JOIN (
            SELECT 
                commune_code,
                ROUND((COUNT(CASE WHEN peb_zone IS NOT NULL THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0))::numeric, 1) as pct_bruit
            FROM transactions
            WHERE est_valide = TRUE
            GROUP BY commune_code
        ) bruit_stats ON bruit_stats.commune_code = c.commune_code
        LEFT JOIN (
            SELECT 
                commune_code,
                ROUND(AVG(
                    CASE classe_ges
                        WHEN 'A' THEN 1.0
                        WHEN 'B' THEN 2.0
                        WHEN 'C' THEN 3.0
                        WHEN 'D' THEN 4.0
                        WHEN 'E' THEN 5.0
                        WHEN 'F' THEN 6.0
                        WHEN 'G' THEN 7.0
                    END
                )::numeric, 1) as avg_ges,
                ROUND(AVG(annee_construction))::integer as avg_annee
            FROM dpe
            WHERE classe_ges IS NOT NULL OR annee_construction IS NOT NULL
            GROUP BY commune_code
        ) dpe_ges_stats ON dpe_ges_stats.commune_code = c.commune_code
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
                
                # Métriques additionnelles
                "revenu_median":  float(r["revenu_median"]) if r["revenu_median"] else None,
                "taux_chomage":   float(r["taux_chomage"]) if r["taux_chomage"] else None,
                "avg_dpe":        float(r["avg_dpe"]) if r["avg_dpe"] else None,
                "pct_bruit":      float(r["pct_bruit"]) if r["pct_bruit"] else 0.0,
                "avg_ges":        float(r["avg_ges"]) if r["avg_ges"] else None,
                "avg_annee":      int(r["avg_annee"]) if r["avg_annee"] else None,
                
                # Valeur à colorer
                "metric_value":   float(r["prix_m2_median"]) if metric == "prix" else
                                  float(r["revenu_median"] or 0.0) if metric == "revenu" else
                                  float(r["taux_chomage"] or 0.0) if metric == "chomage" else
                                  float(r["avg_dpe"] or 0.0) if metric == "dpe" else
                                  float(r["pct_bruit"] or 0.0) if metric == "bruit" else
                                  float(r["avg_ges"] or 0.0) if metric == "ges" else
                                  float(r["avg_annee"] or 0.0) if metric == "annee" else float(r["prix_m2_median"])
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
