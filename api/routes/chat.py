import os
import re
import logging
from flask import Blueprint, request, jsonify
from openai import AzureOpenAI
from ..db import query

bp = Blueprint("chat", __name__)
log = logging.getLogger("chat")

@bp.post("")
def chat_copilot():
    data = request.get_json(force=True) or {}
    messages = data.get("messages", [])

    if not messages:
        return jsonify({"error": "Messages requis"}), 400

    # 1. Vérification des clés Azure OpenAI dans le .env
    api_key = os.getenv("AZURE_OPENAI_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

    # Mode développement : message d'accueil explicatif si l'API n'est pas configurée
    if not api_key or not endpoint or not deployment:
        return jsonify({
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "✨ **Bienvenue sur ImmoBI Copilot !**\n\nJe suis votre assistant immobilier connecté à la base de données. Pour commencer à m'utiliser, veuillez renseigner vos identifiants Azure OpenAI dans votre fichier `.env` :\n\n```env\nAZURE_OPENAI_KEY=votre_cle\nAZURE_OPENAI_ENDPOINT=https://...\nAZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o\n```\n\n*Une fois ces clés définies, je pourrai analyser vos requêtes, interroger la base de données en temps réel pour n'importe quelle ville (comme Vannes, Hennebont ou Nantes), et vous générer des stratégies de négociation en béton armé !*"
                }
            }]
        })

    # 2. Détection de commune dans le dernier message de l'utilisateur (RAG)
    latest_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            latest_user_msg = msg.get("content", "")
            break

    db_context = ""
    if latest_user_msg:
        # Extraire les mots de longueur >= 4
        words = re.findall(r'[a-zA-ZÀ-ÿ\-]+', latest_user_msg)
        candidate_words = [w.strip() for w in words if len(w) >= 4]
        
        matched_communes = []
        for w in candidate_words:
            row = query(
                """
                SELECT commune_code, nom_commune, population, departement_code, revenu_median, taux_chomage 
                FROM communes_stats 
                WHERE nom_commune ILIKE %s 
                LIMIT 1
                """,
                (f"{w}",),
                fetchone=True
            )
            if row and row not in matched_communes:
                matched_communes.append(row)

        # Si des communes correspondent, collecter leurs métriques réelles
        if matched_communes:
            db_context += "=== DONNÉES IMMOBILIÈRES RÉELLES DE LA COMMUNE ===\n"
            for c in matched_communes:
                code = c["commune_code"]
                db_context += f"Ville: {c['nom_commune']} ({c['commune_code']}) - Dept: {c['departement_code']}\n"
                db_context += f"- Population: {c['population']} hab.\n"
                db_context += f"- Revenu médian local: {float(c['revenu_median']) if c['revenu_median'] else 'Donnée non disponible'} €/an\n"
                db_context += f"- Taux de chômage local: {float(c['taux_chomage'])}% (INSEE)\n"
                
                # Prix au m² médian par type
                prices = query(
                    """
                    SELECT type_local, ROUND(AVG(prix_m2_median))::integer as avg_price 
                    FROM prix_m2_par_commune 
                    WHERE commune_code = %s 
                      AND annee = (SELECT MAX(annee) FROM prix_m2_par_commune) 
                    GROUP BY type_local
                    """,
                    (code,)
                )
                if prices:
                    for p in prices:
                        db_context += f"- Prix m² médian ({p['type_local']}): {p['avg_price']} €/m²\n"
                else:
                    db_context += "- Prix m² médian: Non disponible\n"
                
                # Bruit PEB
                noise = query(
                    """
                    SELECT 
                        ROUND(COALESCE(COUNT(CASE WHEN peb_zone IS NOT NULL THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 0)::numeric, 1) as peb_pct,
                        STRING_AGG(DISTINCT peb_aeroport, ', ') FILTER (WHERE peb_aeroport IS NOT NULL) as peb_aeroports
                    FROM transactions
                    WHERE commune_code = %s AND est_valide = TRUE
                    """,
                    (code,),
                    fetchone=True
                )
                if noise and noise["peb_pct"] > 0:
                    db_context += f"- Risque/Nuisance Sonore: {float(noise['peb_pct'])}% des ventes situées dans le PEB de l'aéroport {noise['peb_aeroports']}\n"
                else:
                    db_context += "- Risque/Nuisance Sonore: Calme, préservé des couloirs de bruit réglementaires\n"
                
                # DPE/GES moyens (DPE depuis les transactions réelles, GES depuis la table DPE)
                dpe_ges = query(
                    """
                    SELECT 
                        (
                            SELECT ROUND(AVG(CASE dpe_classe WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 WHEN 'D' THEN 4 WHEN 'E' THEN 5 WHEN 'F' THEN 6 WHEN 'G' THEN 7 END))::integer
                            FROM transactions
                            WHERE commune_code = %s AND est_valide = TRUE AND dpe_classe IS NOT NULL
                        ) as avg_dpe,
                        (
                            SELECT ROUND(AVG(CASE classe_ges WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 WHEN 'D' THEN 4 WHEN 'E' THEN 5 WHEN 'F' THEN 6 WHEN 'G' THEN 7 END))::integer
                            FROM dpe
                            WHERE commune_code = %s AND classe_ges IS NOT NULL
                        ) as avg_ges
                    """,
                    (code, code),
                    fetchone=True
                )
                classes = ["?", "A", "B", "C", "D", "E", "F", "G"]
                if dpe_ges and dpe_ges["avg_dpe"]:
                    db_context += f"- Performance énergétique DPE moyenne: Classe {classes[min(7, max(1, dpe_ges['avg_dpe']))]}\n"
                if dpe_ges and dpe_ges["avg_ges"]:
                    db_context += f"- Émissions Carbone GES moyenne: Classe {classes[min(7, max(1, dpe_ges['avg_ges']))]}\n"
                db_context += "\n"

    # 2.5. Récupération de la date actuelle en français
    from datetime import datetime
    now = datetime.now()
    months_fr = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    date_str = f"{now.day} {months_fr[now.month - 1]} {now.year}"

    # 3. Construction du prompt système enrichi de la base de données
    system_prompt = f"""Tu es ImmoBI Copilot, un assistant virtuel expert en immobilier en France et en négociation d'achat.
Nous sommes aujourd'hui le {date_str}.

Ton rôle est d'analyser les projets immobiliers des utilisateurs, de valider la cohérence de leurs budgets, de leur fournir des synthèses territoriales basées sur des chiffres réels et de rédiger d'excellents arguments ou e-mails de négociation.
Sois chaleureux, pédagogique, précis et structif. Utilise des listes à puces et des caractères gras pour rendre tes réponses très structurées et lisibles.

Si des données spécifiques sont fournies ci-dessous, utilise-les obligatoirement comme l'unique vérité du marché (calculs de prix estimé basés sur la surface, DPE, etc.). Si aucune donnée n'est disponible pour la ville demandée, mentionne-le gentiment et propose des généralités sur le département ou des conseils de négociation génériques.

CONCEPTS CLÉS DE NÉGOCIATION IMMOBILIÈRE :
- Si DPE = F ou G, suggère une décote moyenne des prix de -8% à -15% pour financer les travaux de rénovation (~450 €/m²).
- Si Zone PEB active (bruit), suggère une décote de -5% à -10% liée à la nuisance.
- Si le prix demandé au m² dépasse la médiane locale, conseille de négocier fermement.
"""

    if db_context:
        system_prompt += f"\n{db_context}"

    # 4. Appel client Azure OpenAI
    try:
        client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )
        
        # Injecter le prompt système au début de la conversation
        api_messages = [{"role": "system", "content": system_prompt}] + messages

        try:
            # 1. Tentative standard pour la majorité des modèles (GPT-4o, GPT-3.5, etc.)
            response = client.chat.completions.create(
                model=deployment,
                messages=api_messages,
                max_tokens=800,
                temperature=0.7
            )
        except Exception as first_err:
            first_err_str = str(first_err)
            # 2. Si le modèle rejette 'max_tokens' ou 'temperature' (cas typique des modèles 'o1' de raisonnement)
            if "max_tokens" in first_err_str or "temperature" in first_err_str or "unsupported_parameter" in first_err_str:
                log.warning("Appel standard échoué, tentative de secours pour modèle de raisonnement : %s", first_err)
                response = client.chat.completions.create(
                    model=deployment,
                    messages=api_messages,
                    max_completion_tokens=800
                )
            else:
                raise first_err

        assistant_message = response.choices[0].message.content
        return jsonify({
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": assistant_message
                }
            }]
        })
    except Exception as e:
        log.error("Erreur Azure OpenAI : %s", e)
        return jsonify({
            "error": f"Erreur lors de l'appel de l'intelligence artificielle : {str(e)}"
        }), 500
