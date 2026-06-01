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

# ── Singleton client ───────────────────────────────────────────────────────────
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


# ── Schéma DB injecté dans le prompt SQL ──────────────────────────────────────
_SCHEMA = """
Tables PostgreSQL disponibles (base ImmoBI — données immobilières françaises) :

**transactions** (mutations immobilières DVF) :
  commune_code   TEXT     -- code INSEE de la commune (ex: '56260' pour Vannes)
  date_mutation  DATE     -- date de la vente
  type_local     TEXT     -- 'Appartement', 'Maison', 'Local'
  surface_bati   FLOAT    -- surface habitable en m²
  nb_pieces      INT      -- nombre de pièces
  valeur_fonciere FLOAT   -- prix de vente total en €
  prix_m2        FLOAT    -- prix par m² (peut être NULL)
  dpe_classe     TEXT     -- classe DPE : 'A','B','C','D','E','F','G' (peut être NULL)
  dpe_conso      FLOAT    -- consommation kWh/m²/an
  peb_zone       TEXT     -- zone bruit aéroport (NULL si hors zone)
  peb_aeroport   TEXT     -- nom de l'aéroport (NULL si hors zone)
  dist_gare_m    FLOAT    -- distance gare la plus proche en mètres
  dist_ecole_m   FLOAT    -- distance école la plus proche en mètres
  est_valide     BOOLEAN  -- ⚠ TOUJOURS filtrer WHERE est_valide = TRUE

**communes_stats** (données territoriales INSEE) :
  commune_code   TEXT     -- code INSEE
  nom_commune    TEXT     -- nom en MAJUSCULES ex: 'VANNES', 'LORIENT', 'HENNEBONT'
  departement_code TEXT   -- ex: '56', '29', '35'
  population     INT
  revenu_median  DECIMAL  -- revenu médian annuel €
  taux_chomage   DECIMAL  -- taux chômage %

**dpe** (diagnostics ADEME) :
  commune_code       TEXT
  adresse_normalisee TEXT  -- clé de jointure avec transactions
  classe_energie     TEXT  -- 'A' à 'G'
  conso_energie      FLOAT
  classe_ges         TEXT
  type_batiment      TEXT
  annee_construction INT
  annee_dpe          INT

RÈGLES CRITIQUES :
- nom_commune est en MAJUSCULES → utiliser lower(nom_commune) = 'vannes' pour chercher
- Toujours filtrer: WHERE est_valide = TRUE (sur transactions)
- Toujours utiliser PERCENTILE_CONT(0.5) pour les médianes (jamais AVG pour les prix)
- Limiter avec LIMIT 50 maximum
"""

_SQL_SYSTEM = f"""Tu es un expert SQL PostgreSQL spécialisé en données immobilières.
Ta mission : générer une requête SELECT PostgreSQL pour répondre à la question.

Réponds UNIQUEMENT avec la requête SQL entre balises ```sql ```. Aucun autre texte.

{_SCHEMA}

RÈGLES DE MAPPAGE CRITIQUES ET FILTRES SYSTÉMATIQUES :
1. **Type de logement (type_local)** :
   - Si la question contient "appartement", "appart", "studio", "chambre" -> TOUJOURS filtrer `t.type_local = 'Appartement'`
   - Si la question contient "maison", "pavillon", "villa" -> TOUJOURS filtrer `t.type_local = 'Maison'`
   - Si la question contient "local", "bureau", "commerce" -> TOUJOURS filtrer `t.type_local = 'Local'`

2. **Nombre de pièces (nb_pieces)** :
   - "studio", "T1", "1 pièce" -> `t.nb_pieces = 1`
   - "T2", "2 pièces" -> `t.nb_pieces = 2`
   - "T3", "3 pièces" -> `t.nb_pieces = 3`
   - "T4", "4 pièces" -> `t.nb_pieces = 4`
   - "T5+", "5 pièces et plus" -> `t.nb_pieces >= 5`

3. **Surface habitable (surface_bati)** :
   - "plus de X m²", "au moins X m²" -> `t.surface_bati >= X`
   - "moins de X m²", "maximum X m²" -> `t.surface_bati <= X`
   - "environ X m²", "X m²" -> `t.surface_bati BETWEEN X - 10 AND X + 10`

4. **Nuisance sonore / Zone PEB (peb_zone)** :
   - "au calme", "loin du bruit", "sans bruit", "pas de bruit", "hors zone aéroport" -> TOUJOURS filtrer `t.peb_zone IS NULL`
   - "bruyant", "exposé au bruit", "zone aéroport", "sous aéroport" -> `t.peb_zone IS NOT NULL`

5. **Époque de construction (dpe.annee_construction)** :
   - Si la question mentionne une époque, une année ou un âge de construction, faire obligatoirement un `JOIN dpe d ON t.commune_code = d.commune_code AND t.adresse_normalisee = d.adresse_normalisee` et filtrer sur `d.annee_construction` :
     * "ancien", "très ancien", "avant 1949" -> `d.annee_construction < 1949`
     * "après-guerre", "1949-1974" -> `d.annee_construction BETWEEN 1949 AND 1974`
     * "années 70/80", "1975-1989" -> `d.annee_construction BETWEEN 1975 AND 1989`
     * "années 90", "1990-2000" -> `d.annee_construction BETWEEN 1990 AND 2000`
     * "années 2000", "2001-2012" -> `d.annee_construction BETWEEN 2001 AND 2012`
     * "récent", "après 2012" -> `d.annee_construction > 2012`
     * "neuf", "récent (>=2020)" -> `d.annee_construction >= 2020`

6. **Règles SQL de base** :
   - Toujours filtrer `t.est_valide = TRUE`
   - Toujours utiliser `lower(c.nom_commune) = 'reze'`
   - Toujours utiliser `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ...)` pour le prix médian.

EXEMPLES :

Q: Prix médian appartement à Vannes
```sql
SELECT ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2)::NUMERIC, 0) AS prix_m2_median,
       COUNT(*) AS nb_transactions,
       MAX(EXTRACT(YEAR FROM t.date_mutation))::INT AS annee_max
FROM transactions t
JOIN communes_stats c ON t.commune_code = c.commune_code
WHERE lower(c.nom_commune) = 'vannes'
  AND t.type_local = 'Appartement'
  AND t.est_valide = TRUE
  AND t.prix_m2 IS NOT NULL
```

Q: Prix médian appartement T3 au calme de plus de 60m² construit après 2012 à Rezé
```sql
SELECT ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2)::NUMERIC, 0) AS prix_m2_median,
       COUNT(*) AS nb_transactions
FROM transactions t
JOIN communes_stats c ON t.commune_code = c.commune_code
JOIN dpe d ON t.commune_code = d.commune_code AND t.adresse_normalisee = d.adresse_normalisee
WHERE lower(c.nom_commune) = 'reze'
  AND t.type_local = 'Appartement'
  AND t.nb_pieces = 3
  AND t.surface_bati >= 60
  AND t.peb_zone IS NULL
  AND d.annee_construction > 2012
  AND t.est_valide = TRUE
  AND t.prix_m2 IS NOT NULL
```

Q: Prix d'une maison ancienne de plus de 100m² à Nantes
```sql
SELECT ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2)::NUMERIC, 0) AS prix_m2_median,
       COUNT(*) AS nb_transactions
FROM transactions t
JOIN communes_stats c ON t.commune_code = c.commune_code
JOIN dpe d ON t.commune_code = d.commune_code AND t.adresse_normalisee = d.adresse_normalisee
WHERE lower(c.nom_commune) = 'nantes'
  AND t.type_local = 'Maison'
  AND t.surface_bati >= 100
  AND d.annee_construction < 1949
  AND t.est_valide = TRUE
  AND t.prix_m2 IS NOT NULL
```

Q: Appartement Vannes proche gare, distribution DPE
```sql
SELECT t.dpe_classe,
       COUNT(*) AS nb,
       ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2)::NUMERIC, 0) AS prix_m2_median,
       ROUND(AVG(t.dist_gare_m)::NUMERIC, 0) AS dist_gare_moy_m
FROM transactions t
JOIN communes_stats c ON t.commune_code = c.commune_code
WHERE lower(c.nom_commune) = 'vannes'
  AND t.type_local = 'Appartement'
  AND t.est_valide = TRUE
  AND t.prix_m2 IS NOT NULL
  AND t.dist_gare_m <= 1000
  AND t.dpe_classe IS NOT NULL
GROUP BY t.dpe_classe
ORDER BY t.dpe_classe
```
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_sql(text: str) -> str:
    """Extrait le SQL depuis les balises ```sql ``` ou en brut."""
    m = re.search(r'```sql\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r'```\s*(SELECT|WITH)(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if m:
        return (m.group(1) + m.group(2)).strip()
    text = text.strip()
    if text.upper().startswith(('SELECT', 'WITH')):
        return text
    return ""


def _call_llm_sync(client: AzureOpenAI, deployment: str, messages: list,
                   max_tokens: int = 500, temperature: float = 0.0):
    """Appel LLM non-streaming compatible modèles standard et raisonnement (o1)."""
    try:
        return client.chat.completions.create(
            model=deployment,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except Exception as e:
        err = str(e)
        if any(k in err for k in ("max_tokens", "temperature", "unsupported_parameter")):
            return client.chat.completions.create(
                model=deployment,
                messages=messages,
                max_completion_tokens=max_tokens,
            )
        raise


def _text_to_sql_with_retry(question: str, client: AzureOpenAI,
                             deployment: str, max_retries: int = 3) -> tuple[str, list[dict], str]:
    """
    Phase 1 : génère du SQL depuis la question, l'exécute, retry auto si erreur.
    Retourne (sql_utilisé, résultats, message_erreur)
    """
    conv = [
        {"role": "system", "content": _SQL_SYSTEM},
        {"role": "user",   "content": f"Question: {question}"},
    ]
    last_sql   = ""
    last_error = ""

    for attempt in range(max_retries):
        # Injecter le feedback d'erreur lors des retries
        if last_error and attempt > 0:
            conv.append({"role": "assistant", "content": f"```sql\n{last_sql}\n```"})
            conv.append({
                "role": "user",
                "content": (
                    f"La requête précédente a échoué avec l'erreur PostgreSQL suivante :\n"
                    f"{last_error}\n\n"
                    f"Corrige la requête SQL en tenant compte de cette erreur."
                )
            })
            log.info("[Text-to-SQL] Retry %d/%d — erreur précédente: %s", attempt, max_retries, last_error[:120])

        try:
            resp = _call_llm_sync(client, deployment, conv, max_tokens=600, temperature=0.0)
            raw  = resp.choices[0].message.content or ""
            sql  = _extract_sql(raw)
            last_sql = sql

            if not sql:
                last_error = "Aucun SQL valide extrait de la réponse du modèle."
                log.warning("[Text-to-SQL] Pas de SQL extrait: %s", raw[:200])
                continue

            # Sécurité : SELECT / WITH uniquement
            first_word = sql.strip().split()[0].upper()
            if first_word not in ("SELECT", "WITH"):
                last_error = "Seules les requêtes SELECT/WITH sont autorisées."
                log.warning("[Text-to-SQL] Requête non-SELECT bloquée: %s", sql[:100])
                continue

            log.info("[Text-to-SQL] Tentative %d — SQL: %s", attempt + 1, sql[:150])
            results = query(sql)
            log.info("[Text-to-SQL] ✅ Succès — %d lignes", len(results or []))
            return sql, results or [], ""

        except Exception as e:
            err_str = str(e)
            # Nettoyer l'erreur psycopg2 pour le LLM (garder seulement la première ligne utile)
            last_error = err_str.split('\n')[0].strip()
            log.warning("[Text-to-SQL] Erreur SQL tentative %d: %s", attempt + 1, last_error)

    log.error("[Text-to-SQL] Échec après %d tentatives. Dernière erreur: %s", max_retries, last_error)
    return last_sql, [], last_error


def _format_results_as_context(results: list[dict], sql: str, error: str) -> str:
    """Formate les résultats SQL en bloc de contexte lisible pour le LLM."""
    if error and not results:
        return (
            f"⚠ Aucune donnée disponible (erreur après {3} tentatives SQL).\n"
            f"Erreur : {error}\n"
            f"Informe l'utilisateur que tu ne peux pas répondre précisément "
            f"et suggère de reformuler la question avec un nom de commune.\n"
        )

    if not results:
        return "Aucun résultat trouvé dans la base de données pour cette requête.\n"

    cols = list(results[0].keys())
    ctx  = "=== RÉSULTATS REQUÊTE BASE IMMOBI ===\n"
    ctx += f"SQL : {sql[:300]}{'...' if len(sql) > 300 else ''}\n"
    ctx += f"Lignes retournées : {len(results)}\n\n"

    # En-tête
    ctx += " | ".join(cols) + "\n"
    ctx += "-" * min(80, sum(len(c) + 3 for c in cols)) + "\n"

    # Données (max 30 lignes)
    for row in results[:30]:
        ctx += " | ".join(
            str(round(float(v), 2)) if isinstance(v, float) else str(v)
            for v in row.values()
        ) + "\n"

    if len(results) > 30:
        ctx += f"... ({len(results) - 30} lignes supplémentaires non affichées)\n"

    return ctx


def _build_system_prompt(db_context: str) -> str:
    months_fr = ["janvier","février","mars","avril","mai","juin",
                 "juillet","août","septembre","octobre","novembre","décembre"]
    now = datetime.now()
    date_str = f"{now.day} {months_fr[now.month - 1]} {now.year}"

    prompt = f"""Tu es ImmoBI Copilot, un outil d'aide à la négociation immobilière.
Date : {date_str}.

## MISSION
Transformer les données de la base ImmoBI en arguments de négociation concrets et chiffrés.
Tu es un outil, PAS un assistant conversationnel. Sois direct, précis, utile.

## FORMAT DE RÉPONSE OBLIGATOIRE (S'IL Y A UNE SEULE VILLE)
Réponds TOUJOURS avec ce format exact en indiquant clairement le nom de la ville en question dans le titre du Verdict et du Prix de référence :

**🎯 Verdict à [Nom de la ville]** : [1 phrase tranchée : bon deal / marché tendu / fort levier de négo]

**📊 Prix de référence à [Nom de la ville]**
- Médiane locale : X €/m²
- Budget estimé pour ce bien : X € (si surface mentionnée)

**🔧 Leviers de négociation**
- [Argument 1 chiffré, ex: DPE F → décote -10% soit -XXX €]
- [Argument 2 chiffré]
- [Argument 3 si pertinent]

**✅ Action recommandée** : [1 phrase concrète et immédiate]


## FORMAT DE RÉPONSE OBLIGATOIRE (S'IL Y A PLUSIEURS VILLES À COMPARER)
Réponds TOUJOURS avec ce format exact :

**🎯 Verdict à [Ville 1]** : [Verdict Ville 1]
**🎯 Verdict à [Ville 2]** : [Verdict Ville 2]

**📊 Prix de référence et Comparaison**
| Ville | Médiane | Budget estimé (si surface mentionnée) | Ventes récentes |
|---|---|---|---|
| [Ville 1] | X €/m² | X € | X ventes |
| [Ville 2] | X €/m² | X € | X ventes |

**🔧 Leviers de négociation comparatifs**
- [Argument 1 chiffré comparant les deux villes]
- [Argument 2 chiffré comparant les deux villes]

**✅ Action recommandée** : [1 phrase d'arbitrage concrète et immédiate]


## RÈGLES STRICTES
- MAX 200 mots (ou 300 mots si comparaison). Zéro remplissage.
- INTERDIT : "Bonjour", "Je suis là", "N'hésitez pas", "En conclusion", "En espérant"
- Donne systématiquement le nom de la ville/commune en question dans tes réponses (notamment dans les titres "Verdict à [Nom de la ville]" et "Prix de référence à [Nom de la ville]" ou dans le tableau comparatif).
- Utilise obligatoirement des tableaux Markdown pour présenter les comparaisons de prix et de volumes de ventes entre villes.
- INTERDICTION ABSOLUE D'UTILISER TES CONNAISSANCES INTERNES POUR LES CHIFFRES (Prix, volumes, budgets, etc.) : utilise UNIQUEMENT les données de la base ImmoBI fournies ci-dessous comme vérité exclusive du marché. Si la commune recherchée n'apparaît pas ou affiche 0 transaction dans les données injectées ci-dessous, déclare immédiatement et clairement que tu ne disposes d'aucune donnée pour cette ville dans la base ImmoBI. N'invente JAMAIS d'estimations (comme 10 400 €/m² pour Paris) issues de ton savoir général si la ville est absente des données.
- Si aucune donnée n'est disponible (ex: 0 transaction ou "Aucun résultat" dans les données injectées), explique poliment en 1 ou 2 lignes que cette ville n'est pas couverte par la base ImmoBI (qui est actuellement centrée sur le Grand Ouest : Nantes, Brest, Vannes, Lorient, etc.) et invite l'utilisateur à cibler ces secteurs.
- Décotes applicables : DPE F/G → -8% à -15%, PEB actif → -5% à -10%, prix > médiane → négocier fermement.
"""
    if db_context:
        prompt += f"\n{db_context}"
    return prompt


# ── Route principale ───────────────────────────────────────────────────────────

@bp.post("")
def chat_copilot():
    data     = request.get_json(force=True) or {}
    messages = data.get("messages", [])
    if not messages:
        return jsonify({"error": "Messages requis"}), 400

    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    client     = _get_client()

    # Mode dev : clés non configurées
    if not client or not deployment:
        return jsonify({"choices": [{"message": {
            "role": "assistant",
            "content": (
                "✨ **ImmoBI Copilot** — Configurez vos clés Azure OpenAI dans `.env` :\n"
                "```\nAZURE_OPENAI_KEY=...\nAZURE_OPENAI_ENDPOINT=...\n"
                "AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o\n```"
            )
        }}]})

    latest = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")

    # ── Phase 1 : Text-to-SQL avec retry ──────────────────────────────────────
    sql_used, db_results, sql_error = _text_to_sql_with_retry(latest, client, deployment)
    db_context    = _format_results_as_context(db_results, sql_used, sql_error)
    system_prompt = _build_system_prompt(db_context)
    api_messages  = [{"role": "system", "content": system_prompt}] + messages

    # ── Phase 2 : Réponse en streaming ────────────────────────────────────────
    def generate():
        try:
            try:
                stream = client.chat.completions.create(
                    model=deployment,
                    messages=api_messages,
                    max_tokens=1400,
                    temperature=0.7,
                    stream=True,
                )
            except Exception as e:
                err = str(e)
                if any(k in err for k in ("max_tokens", "temperature", "unsupported_parameter")):
                    stream = client.chat.completions.create(
                        model=deployment,
                        messages=api_messages,
                        max_completion_tokens=1400,
                        stream=True,
                    )
                else:
                    raise

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield f"data: {json.dumps({'c': chunk.choices[0].delta.content})}\n\n"

        except Exception as e:
            log.error("Erreur Azure OpenAI (streaming) : %s", e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
