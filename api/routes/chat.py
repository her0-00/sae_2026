import os
import re
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, Response, stream_with_context
from openai import AzureOpenAI
from ..db import query

bp = Blueprint("chat", __name__)
log = logging.getLogger("chat")

# ── Singleton client — créé une seule fois, réutilisé sur toutes les requêtes ──
_client: AzureOpenAI | None = None

def _get_client() -> AzureOpenAI | None:
    global _client
    if _client is not None:
        return _client
    api_key  = os.getenv("AZURE_OPENAI_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    version  = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    if api_key and endpoint:
        _client = AzureOpenAI(api_key=api_key, api_version=version, azure_endpoint=endpoint)
    return _client


def _build_db_context(message: str) -> str:
    """
    Détecte les noms de communes dans le message et retourne un bloc
    de contexte enrichi en une seule requête SQL.
    """
    words = re.findall(r'[a-zA-ZÀ-ÿ\-]+', message)
    candidates = list({w.lower() for w in words if len(w) >= 4})
    if not candidates:
        return ""

    # Une seule requête qui récupère tout : communes + prix + bruit + DPE
    rows = query(
        """
        SELECT
            c.commune_code,
            c.nom_commune,
            c.departement_code,
            c.population,
            c.revenu_median,
            c.taux_chomage,
            (SELECT ROUND(AVG(p.prix_m2_median))::integer
             FROM prix_m2_par_commune p
             WHERE p.commune_code = c.commune_code
               AND p.type_local = 'Appartement'
               AND p.annee = (SELECT MAX(annee) FROM prix_m2_par_commune
                              WHERE commune_code = c.commune_code)
            ) AS prix_appart,
            (SELECT ROUND(AVG(p.prix_m2_median))::integer
             FROM prix_m2_par_commune p
             WHERE p.commune_code = c.commune_code
               AND p.type_local = 'Maison'
               AND p.annee = (SELECT MAX(annee) FROM prix_m2_par_commune
                              WHERE commune_code = c.commune_code)
            ) AS prix_maison,
            (SELECT ROUND(COALESCE(
                COUNT(CASE WHEN t.peb_zone IS NOT NULL THEN 1 END) * 100.0
                / NULLIF(COUNT(*), 0), 0)::numeric, 1)
             FROM transactions t
             WHERE t.commune_code = c.commune_code AND t.est_valide = TRUE
            ) AS peb_pct,
            (SELECT STRING_AGG(DISTINCT t.peb_aeroport, ', ')
                    FILTER (WHERE t.peb_aeroport IS NOT NULL)
             FROM transactions t
             WHERE t.commune_code = c.commune_code AND t.est_valide = TRUE
            ) AS peb_aeroports,
            (SELECT ROUND(AVG(
                CASE d.dpe_classe
                  WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3
                  WHEN 'D' THEN 4 WHEN 'E' THEN 5 WHEN 'F' THEN 6 WHEN 'G' THEN 7
                END))::integer
             FROM transactions d
             WHERE d.commune_code = c.commune_code
               AND d.est_valide = TRUE AND d.dpe_classe IS NOT NULL
            ) AS avg_dpe
        FROM communes_stats c
        WHERE lower(c.nom_commune) = ANY(%s)
        LIMIT 3
        """,
        (candidates,)
    )

    if not rows:
        return ""

    CLASSES = ["?", "A", "B", "C", "D", "E", "F", "G"]
    ctx = "=== DONNÉES IMMOBILIÈRES RÉELLES ===\n"
    for r in rows:
        ctx += f"Ville : {r['nom_commune']} ({r['commune_code']}) — Dept. {r['departement_code']}\n"
        ctx += f"- Population : {r['population']} hab.\n"
        ctx += f"- Revenu médian : {float(r['revenu_median']) if r['revenu_median'] else 'N/D'} €/an\n"
        ctx += f"- Taux de chômage : {float(r['taux_chomage']) if r['taux_chomage'] else 'N/D'} %\n"
        if r['prix_appart']:
            ctx += f"- Prix m² médian Appartement : {r['prix_appart']} €/m²\n"
        if r['prix_maison']:
            ctx += f"- Prix m² médian Maison : {r['prix_maison']} €/m²\n"
        peb = float(r['peb_pct']) if r['peb_pct'] else 0
        if peb > 0:
            ctx += f"- Nuisance sonore PEB : {peb}% des ventes (aéroport {r['peb_aeroports']})\n"
        else:
            ctx += "- Nuisance sonore : Aucune zone PEB détectée\n"
        if r['avg_dpe']:
            idx = min(7, max(1, r['avg_dpe']))
            ctx += f"- DPE moyen : Classe {CLASSES[idx]}\n"
        ctx += "\n"
    return ctx


def _build_system_prompt(db_context: str) -> str:
    months_fr = ["janvier","février","mars","avril","mai","juin",
                 "juillet","août","septembre","octobre","novembre","décembre"]
    now = datetime.now()
    date_str = f"{now.day} {months_fr[now.month - 1]} {now.year}"

    prompt = f"""Tu es ImmoBI Copilot, un assistant expert en immobilier en France et en négociation d'achat.
Nous sommes le {date_str}.

Rôle : analyser des projets immobiliers, valider des budgets, fournir des synthèses territoriales chiffrées, rédiger des arguments de négociation.
Style : chaleureux, structuré, précis. Utilise des listes à puces et du gras. Réponses concises.

Règles de négociation :
- DPE F ou G → décote -8% à -15% pour financer les travaux (~450 €/m²).
- Zone PEB active → décote -5% à -10%.
- Prix demandé > médiane locale → conseille de négocier fermement.

Si des données sont fournies ci-dessous, utilise-les comme unique vérité du marché.
"""
    if db_context:
        prompt += f"\n{db_context}"
    return prompt


@bp.post("")
def chat_copilot():
    data = request.get_json(force=True) or {}
    messages = data.get("messages", [])
    if not messages:
        return jsonify({"error": "Messages requis"}), 400

    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    client = _get_client()

    # Mode dev : clés non configurées
    if not client or not deployment:
        return jsonify({"choices": [{"message": {
            "role": "assistant",
            "content": "✨ **ImmoBI Copilot** — Configurez vos clés Azure OpenAI dans `.env` :\n```\nAZURE_OPENAI_KEY=...\nAZURE_OPENAI_ENDPOINT=...\nAZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o\n```"
        }}]})

    # Extraction du dernier message utilisateur
    latest = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")

    # Contexte DB en 1 seule requête
    db_context = _build_db_context(latest) if latest else ""
    system_prompt = _build_system_prompt(db_context)
    api_messages = [{"role": "system", "content": system_prompt}] + messages

    # ── Streaming SSE ──────────────────────────────────────────────
    def generate():
        try:
            try:
                stream = client.chat.completions.create(
                    model=deployment,
                    messages=api_messages,
                    max_tokens=600,
                    temperature=0.7,
                    stream=True,
                )
            except Exception as e:
                err = str(e)
                if any(k in err for k in ("max_tokens", "temperature", "unsupported_parameter")):
                    stream = client.chat.completions.create(
                        model=deployment,
                        messages=api_messages,
                        max_completion_tokens=600,
                        stream=True,
                    )
                else:
                    raise

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield f"data: {json.dumps({'c': chunk.choices[0].delta.content})}\n\n"

        except Exception as e:
            log.error("Erreur Azure OpenAI : %s", e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
