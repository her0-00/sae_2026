from flask import Blueprint, request, jsonify, abort
from ..db import query

bp = Blueprint("estimateur", __name__)


@bp.post("")
def estimer():
    data = request.get_json(force=True) or {}
    commune_code = data.get("commune_code")
    surface = data.get("surface")
    type_local = data.get("type_local", "Appartement")

    if not commune_code or not surface:
        abort(422)

    try:
        surface = float(surface)
    except (ValueError, TypeError):
        abort(422)

    # Statistiques de la commune pour ce type de bien (12 derniers mois)
    stats = query(
        """
        SELECT
            COUNT(*)                                                AS nb_comparables,
            ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY prix_m2)::NUMERIC, 0) AS q25,
            ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY prix_m2)::NUMERIC, 0) AS median,
            ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY prix_m2)::NUMERIC, 0) AS q75
        FROM transactions
        WHERE commune_code = %s
          AND type_local   = %s
          AND est_valide   = TRUE
          AND prix_m2 IS NOT NULL
          AND date_mutation >= NOW() - INTERVAL '24 months'
        """,
        (commune_code, type_local),
        fetchone=True,
    )

    if not stats or not stats["median"]:
        return jsonify({"error": "Pas assez de données pour cette commune"}), 404

    median = float(stats["median"])
    q25 = float(stats["q25"])
    q75 = float(stats["q75"])

    prix_estime = median * surface
    fourchette_basse = q25 * surface
    fourchette_haute = q75 * surface

    # Score si un prix demandé est fourni
    prix_demande = data.get("prix_demande")
    score_deal = None
    if prix_demande:
        try:
            pm2_demande = float(prix_demande) / surface
            if pm2_demande <= q25:
                score_deal = "excellent"
            elif pm2_demande <= median:
                score_deal = "bon"
            elif pm2_demande <= q75:
                score_deal = "correct"
            else:
                score_deal = "cher"
        except (ValueError, TypeError):
            pass

    return jsonify({
        "commune_code":      commune_code,
        "type_local":        type_local,
        "surface":           surface,
        "prix_m2_median":    median,
        "prix_m2_q25":       q25,
        "prix_m2_q75":       q75,
        "prix_estime":       round(prix_estime),
        "fourchette_basse":  round(fourchette_basse),
        "fourchette_haute":  round(fourchette_haute),
        "nb_comparables":    int(stats["nb_comparables"]),
        "score_deal":        score_deal,
    })
