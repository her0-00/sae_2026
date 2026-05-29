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

    # ── ENRICHISSEMENT : CONTEXTE LOCAL ──
    # 1. Proximité Transports & Écoles
    prox = query(
        """
        SELECT 
            ROUND(AVG(dist_gare_m))::integer as avg_dist_gare_m,
            ROUND(AVG(dist_ecole_m))::integer as avg_dist_ecole_m,
            MIN(dist_gare_m) as min_dist_gare_m,
            MIN(dist_ecole_m) as min_dist_ecole_m
        FROM transactions
        WHERE commune_code = %s AND est_valide = TRUE
        """,
        (commune_code,),
        fetchone=True
    ) or {}

    # 2. Exposition au Bruit Aéroport (PEB)
    noise = query(
        """
        SELECT 
            ROUND(COALESCE(COUNT(CASE WHEN peb_zone IS NOT NULL THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 0)::numeric, 1) as peb_pct,
            STRING_AGG(DISTINCT peb_aeroport, ', ') FILTER (WHERE peb_aeroport IS NOT NULL) as peb_aeroports
        FROM transactions
        WHERE commune_code = %s AND est_valide = TRUE
        """,
        (commune_code,),
        fetchone=True
    ) or {}

    # 3. Profil Socio-Économique (INSEE)
    socio = query(
        "SELECT population, revenu_median, taux_chomage FROM communes_stats WHERE commune_code = %s",
        (commune_code,),
        fetchone=True
    ) or {}

    # 4. Distribution DPE Commune (pour comparaison locale)
    dpe_rows = query(
        """
        SELECT dpe_classe, COUNT(*) as count
        FROM transactions
        WHERE commune_code = %s AND type_local = %s AND dpe_classe IS NOT NULL AND est_valide = TRUE
        GROUP BY dpe_classe
        ORDER BY dpe_classe
        """,
        (commune_code, type_local)
    )

    dpe_dist = {r["dpe_classe"]: int(r["count"]) for r in dpe_rows} if dpe_rows else {}

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
        
        # Données enrichies de contexte
        "proximite": {
            "avg_dist_gare_m":  prox.get("avg_dist_gare_m"),
            "avg_dist_ecole_m": prox.get("avg_dist_ecole_m"),
            "min_dist_gare_m":  prox.get("min_dist_gare_m"),
            "min_dist_ecole_m": prox.get("min_dist_ecole_m"),
        },
        "bruit": {
            "peb_pct":          float(noise.get("peb_pct") or 0.0),
            "peb_aeroports":    noise.get("peb_aeroports") or None,
        },
        "socio": {
            "population":       int(socio.get("population") or 0) if socio.get("population") else None,
            "revenu_median":    float(socio.get("revenu_median") or 0.0) if socio.get("revenu_median") else None,
            "taux_chomage":     float(socio.get("taux_chomage") or 0.0) if socio.get("taux_chomage") else None,
        },
        "dpe_dist": dpe_dist
    })

