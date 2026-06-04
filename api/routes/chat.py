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
  adresse        TEXT     -- adresse du bien (ex: '12 RUE DES ALIZES')
  adresse_normalisee TEXT  -- adresse normalisée du bien
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
  longitude      FLOAT    -- coordonnée géographique longitude du bien
  latitude       FLOAT    -- coordonnée géographique latitude du bien
  est_valide     BOOLEAN  -- ⚠ TOUJOURS filtrer WHERE est_valide = TRUE

**communes_stats** (données territoriales INSEE) :
  commune_code   TEXT     -- code INSEE
  nom_commune    TEXT     -- nom en casse mixte ex: 'Vannes', 'Lorient', 'Bouvron', 'Hennebont'
  departement_code TEXT   -- ex: '56', '29', '35'
  population     INT
  revenu_median  DECIMAL  -- revenu médian annuel €
  taux_chomage   DECIMAL  -- taux chômage %

**communes_loyers** (indicateurs de loyers d'annonce par commune en 2025) :
  commune_code         TEXT     -- code INSEE de la commune
  nom_commune          TEXT     -- nom de la commune
  loyer_m2_appartement FLOAT    -- loyer médian estimé par m² pour un appartement
  loyer_m2_maison      FLOAT    -- loyer médian estimé par m² pour une maison

**dpe** (diagnostics ADEME) :
  commune_code       TEXT
  adresse_normalisee TEXT  -- clé de jointure avec transactions
  classe_energie     TEXT  -- 'A' à 'G'
  conso_energie      FLOAT
  classe_ges         TEXT
  type_batiment      TEXT
  annee_construction INT
  annee_dpe          INT

**points_interet** (équipements de proximité géolocalisés — source OpenStreetMap) :
  id                 SERIAL PRIMARY KEY
  type               TEXT     -- type d'équipement : 'gare', 'ecole', 'universite', 'cinema', 'salle_sport', 'restaurant', 'pharmacie', 'commerce', 'transport', 'parking'
  nom                TEXT     -- nom de l'équipement (peut être NULL)
  commune_code       TEXT     -- code INSEE de la commune (peut être NULL)
  latitude           FLOAT
  longitude          FLOAT
  geom               GEOMETRY(Point, 4326)  -- point géographique PostGIS

  ⚠ Pour filtrer les POI d'une commune : JOIN communes_stats c ON ST_Within(p.geom, c.geom) — NE PAS utiliser departement_code qui n'existe pas.
  ⚠ Pour toute recherche ou sélection de points d'intérêt (points_interet) : TOUJOURS exclure les points sans nom avec la condition `nom IS NOT NULL AND nom <> ''`.

- Pour trouver un POI par nom et s'en servir comme point de référence spatial : utiliser une sous-requête sur points_interet. Exemple pour trouver des transactions près d'un Basic-Fit à Vannes :
  ```sql
  SELECT t.latitude, t.longitude, t.adresse, t.valeur_fonciere, t.type_local, t.dpe_classe, t.prix_m2, t.surface_bati
  FROM transactions t
  JOIN communes_stats c ON t.commune_code = c.commune_code
  WHERE translate(lower(c.nom_commune), 'âàäéèêëîïôöûüùç', 'aaaeeeeiioouuuc') = 'vannes'
    AND t.type_local = 'Appartement'
    AND t.est_valide = TRUE
    AND t.date_mutation >= NOW() - INTERVAL '24 months'
    AND ST_DWithin(
      t.geom::geography,
      (SELECT geom::geography FROM points_interet
       WHERE type = 'salle_sport' AND replace(replace(lower(COALESCE(nom,'')), '-', ''), ' ', '') = 'basicfit'
       ORDER BY geom <-> (SELECT ST_Centroid(geom) FROM communes_stats WHERE lower(nom_commune)='vannes') LIMIT 1),
      2000
    )
  LIMIT 1000
  ```
- Si la question porte sur plusieurs POIs de référence (ex: "un Fitness Park ou un Basic Fit"), utiliser EXISTS avec une sous-requête pour trouver les transactions à proximité de l'un ou l'autre de ces POIs :
  ```sql
  SELECT t.latitude, t.longitude, t.adresse, t.valeur_fonciere, t.type_local, t.dpe_classe, t.prix_m2, t.surface_bati
  FROM transactions t
  JOIN communes_stats c ON t.commune_code = c.commune_code
  WHERE translate(lower(c.nom_commune), 'âàäéèêëîïôöûüùç', 'aaaeeeeiioouuuc') = 'vannes'
    AND t.est_valide = TRUE
    AND t.date_mutation >= NOW() - INTERVAL '24 months'
    AND EXISTS (
      SELECT 1 FROM points_interet p
      WHERE p.type = 'salle_sport'
        AND replace(replace(lower(COALESCE(p.nom,'')), '-', ''), ' ', '') IN ('fitnesspark', 'basicfit')
        AND ST_DWithin(t.geom::geography, p.geom::geography, 2000)
    )
  LIMIT 1000
  ```
- IMPORTANT : pour les recherches spatiales autour d'un POI, utiliser un rayon de 2000m par défaut.
- Pour rechercher un POI par nom, normaliser avec `replace(replace(lower(COALESCE(nom,'')), '-', ''), ' ', '')` et comparer avec le nom sans tirets ni espaces (ex: 'basicfit', 'fitnespark'). Ne JAMAIS utiliser LIKE/ILIKE avec le caractère `%`.
- IMPORTANT POUR LES GARES : Le nom d'une gare (type = 'gare') dans la base de données correspond uniquement au nom de la commune elle-même (ex: 'vannes' pour la gare de Vannes, 'nantes' pour la gare de Nantes, 'chantenay' pour la gare de Chantenay). Donc, pour chercher la gare de Vannes, filtrer par type = 'gare' et par le nom de la ville : `type = 'gare' AND replace(replace(lower(COALESCE(nom,'')), '-', ''), ' ', '') = 'vannes'`. Ne JAMAIS chercher 'garedevannes' ou 'garedenantes' dans le nom du POI.
- Pour tout POI référencé dans points_interet : TOUJOURS utiliser une sous-requête pour récupérer ses coordonnées, ne jamais inventer de coordonnées GPS.
- **Rues et Adresses** : Si l'utilisateur mentionne une rue ou une adresse (ex: 'Rue du Four', 'Rue de la Paix', 'Rue des Alizés'), ce n'est PAS un point d'intérêt (`points_interet`). Pour filtrer les transactions sur cette rue ou pour trouver ses coordonnées spatiales de référence, utiliser la clause `t.adresse_normalisee LIKE '%nom_de_la_rue%'` (ex: `t.adresse_normalisee LIKE '%rue du four%'`) sur la table `transactions` (ou `dpe`). Ne jamais chercher une rue/adresse dans la table `points_interet`.
  - Types disponibles et leur signification :
    * 'gare' : Gare ferroviaire SNCF
    * 'ecole' : Établissement scolaire (primaire, collège, lycée)
    * 'universite' : Université ou grande école
    * 'cinema' : Cinéma
    * 'salle_sport' : Salle de sport, gymnase, piscine
    * 'restaurant' : Restaurant, café, brasserie
    * 'pharmacie' : Pharmacie
    * 'commerce' : Supermarché, boulangerie, commerce de proximité
    * 'transport' : Arrêt de bus ou de tramway
    * 'parking' : Parking public
- ⚠ **Aéroports** : Le type `'aeroport'` n'existe PAS dans `points_interet`. Les aéroports ne sont présents que dans la table `transactions` (colonne `peb_aeroport`). Pour obtenir les aéroports avec leur localisation moyenne (nécessaire pour les afficher sur la carte), utiliser :
  `SELECT peb_aeroport AS nom, AVG(latitude) AS latitude, AVG(longitude) AS longitude, 'aeroport' AS type FROM transactions WHERE peb_aeroport IS NOT NULL GROUP BY peb_aeroport`


RÈGLES CRITIQUES :
- nom_commune est en **casse mixte** (ex: 'Vannes', 'Bouvron') → TOUJOURS utiliser lower(nom_commune) pour comparer
- Toujours filtrer: WHERE est_valide = TRUE (sur transactions)
- Toujours utiliser PERCENTILE_CONT(0.5) pour les médianes (jamais AVG pour les prix)
- Pour toute recherche de gare ferroviaire (train station) : utiliser impérativement type = 'gare' (et non 'transport' qui désigne uniquement les arrêts de bus).
- Limites de lignes : Pour les requêtes textuelles classiques, limiter à 50 maximum. Pour les requêtes cartographiques (quand l'utilisateur demande une carte, de situer, ou de localiser), utiliser un LIMIT 1000 et s'assurer de sélectionner latitude et longitude dans le SELECT.
- Agrégation pour graphiques : Si l'utilisateur demande un graphique, une évolution, une distribution ou une répartition, utiliser des fonctions d'agrégation (comme COUNT(*), AVG(), ou PERCENTILE_CONT(0.5)) et un GROUP BY approprié (par exemple par classe DPE dpe_classe, par type local type_local, ou par trimestre date_trunc('quarter', date_mutation) ou par année). Ne jamais renvoyer des dizaines de lignes individuelles si la question demande une vue d'ensemble ou une comparaison graphique.
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
   - Toujours normaliser et comparer les noms de communes sans accents en utilisant la fonction `translate()` (qui est la seule disponible en base de données, l'extension unaccent n'étant pas activée) :
     `translate(lower(c.nom_commune), 'âàäéèêëîïôöûüùç', 'aaaeeeeiioouuuc') = 'reze'`
   - **Cohérence temporelle des prix** : Pour s'aligner sur l'estimateur de la page principale et refléter la valeur récente du marché, restreindre les transactions aux 24 derniers mois :
     `AND t.date_mutation >= NOW() - INTERVAL '24 months'`
     Si et seulement si la question est très spécifique ou comporte de nombreux filtres croisés (ce qui risque de renvoyer 0 résultat avec 24 mois), utiliser un intervalle plus large de 5 ans pour avoir un échantillon suffisant :
     `AND t.date_mutation >= NOW() - INTERVAL '60 months'` (soit 60 mois)
   - Toujours utiliser `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ...)` pour le prix médian.
   - **Fiabilité statistique par commune** : Pour tout calcul, sous-requête, ou regroupement (GROUP BY) par commune destiné à calculer des médianes de prix ou des rendements locatifs, filtrer impérativement pour n'inclure que les communes ayant au moins 3 transactions valides sur la période afin d'éviter les anomalies statistiques dues à des ventes uniques ou atypiques (comme des caves, parkings ou ruines vendus à très bas prix). Utiliser la clause : `HAVING COUNT(*) >= 3`.
   - ⚠ **Arrondi et types de données (ROUND)** : PostgreSQL ne possède PAS de fonction `ROUND(double precision, integer)`. La fonction `ROUND(valeur, decimales)` n'est définie que pour le type `NUMERIC`. Par conséquent, pour arrondir un champ de type `FLOAT`/`double precision` (comme `loyer_m2_appartement`, `loyer_m2_maison` ou `prix_m2`) avec un nombre spécifique de décimales, tu DOIS obligatoirement caster l'expression en `NUMERIC` avant d'appeler `ROUND()`. Exemple : `ROUND((l.loyer_m2_appartement * 18)::NUMERIC, 2)` ou `ROUND(CAST(expression AS NUMERIC), 2)`.
   - **Plus cher / Prix total vs Prix au m²** :
      * Si la question porte sur le bien "le plus cher", "le plus de valeur", ou "le top des biens les plus chers", trier par le prix d'achat total `t.valeur_fonciere` (ex: `ORDER BY t.valeur_fonciere DESC`).
      * Si la question porte sur "le plus cher au m²" ou "le prix au m² le plus élevé", trier par le prix par m² `t.prix_m2` (ex: `ORDER BY t.prix_m2 DESC`).
   - **Géolocalisation & Cartographie** :
     * Pour les transactions, si la question demande d'afficher une carte, de situer ou localiser des biens (ou demande des transactions avec coordonnées/repères), tu DOIS obligatoirement inclure `t.latitude`, `t.longitude`, `t.adresse`, `t.valeur_fonciere`, `t.type_local` et `t.dpe_classe` dans la clause SELECT pour que l'application puisse les positionner, afficher leur adresse et permettre le filtrage interactif.
     * Pour les points d'intérêt (points_interet), si la question demande de les afficher ou de les situer, tu DOIS obligatoirement inclure `nom`, `latitude`, `longitude` et `type` dans la clause SELECT pour que l'application puisse les positionner, afficher leur nom et utiliser l'icône correcte (ex: gare, ecole, salle_sport, etc.).

    7. **Loyers et Rendement Locatif (communes_loyers)** :
       - Pour toute question sur les loyers (ex: loyer moyen, loyer par m²), faire une jointure ou une requête sur `communes_loyers`. Si la question porte sur un appartement, utiliser `loyer_m2_appartement`. Si elle porte sur une maison, utiliser `loyer_m2_maison`.
       - Pour calculer le rendement locatif brut d'un type de bien (ex: Appartement) dans une commune, utiliser un CTE pour obtenir le prix médian et filtrer `HAVING COUNT(*) >= 3` afin d'éviter les valeurs aberrantes (outliers), puis calculer le rendement en castant le résultat en NUMERIC :
         `ROUND(((l.loyer_m2_appartement * 12 / s.prix_m2_median) * 100)::NUMERIC, 2)` en joignant `communes_loyers` (l) et le CTE (s).
         Si le prix d'achat ou le loyer mensuel total est spécifié dans la question, appliquer la formule standard : `((loyer_mensuel * 12) / prix_achat) * 100`.

EXEMPLES :

Q: Quel est le loyer moyen d'un appartement à Vannes ?
```sql
SELECT loyer_m2_appartement
FROM communes_loyers
WHERE translate(lower(nom_commune), 'âàäéèêëîïôöûüùç', 'aaaeeeeiioouuuc') = 'vannes'
```

Q: Rendement locatif brut moyen d'un appartement à Vannes
```sql
WITH stats AS (
  SELECT t.commune_code,
         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2) AS prix_m2_median
  FROM transactions t
  WHERE t.type_local = 'Appartement'
    AND t.est_valide = TRUE
    AND t.prix_m2 IS NOT NULL
    AND t.date_mutation >= NOW() - INTERVAL '24 months'
  GROUP BY t.commune_code
  HAVING COUNT(*) >= 3
)
SELECT l.loyer_m2_appartement,
       ROUND(s.prix_m2_median::NUMERIC, 0) AS prix_m2_median,
       ROUND(((l.loyer_m2_appartement * 12 / s.prix_m2_median) * 100)::NUMERIC, 2) AS rendement_locatif_brut
FROM communes_loyers l
JOIN stats s ON l.commune_code = s.commune_code
WHERE translate(lower(l.nom_commune), 'âàäéèêëîïôöûüùç', 'aaaeeeeiioouuuc') = 'vannes'
```

Q: Prix médian appartement à Vannes
```sql
SELECT ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2)::NUMERIC, 0) AS prix_m2_median,
       COUNT(*) AS nb_transactions,
       MAX(EXTRACT(YEAR FROM t.date_mutation))::INT AS annee_max
FROM transactions t
JOIN communes_stats c ON t.commune_code = c.commune_code
WHERE translate(lower(c.nom_commune), 'âàäéèêëîïôöûüùç', 'aaaeeeeiioouuuc') = 'vannes'
  AND t.type_local = 'Appartement'
  AND t.est_valide = TRUE
  AND t.prix_m2 IS NOT NULL
  AND t.date_mutation >= NOW() - INTERVAL '24 months'
```

Q: Prix médian appartement T3 au calme de plus de 60m² construit après 2012 à Rezé
```sql
SELECT ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2)::NUMERIC, 0) AS prix_m2_median,
       COUNT(*) AS nb_transactions
FROM transactions t
JOIN communes_stats c ON t.commune_code = c.commune_code
JOIN dpe d ON t.commune_code = d.commune_code AND t.adresse_normalisee = d.adresse_normalisee
WHERE translate(lower(c.nom_commune), 'âàäéèêëîïôöûüùç', 'aaaeeeeiioouuuc') = 'reze'
  AND t.type_local = 'Appartement'
  AND t.nb_pieces = 3
  AND t.surface_bati >= 60
  AND t.peb_zone IS NULL
  AND d.annee_construction > 2012
  AND t.est_valide = TRUE
  AND t.prix_m2 IS NOT NULL
  AND t.date_mutation >= NOW() - INTERVAL '60 months'
```

Q: Prix d'une maison ancienne de plus de 100m² à Nantes
```sql
SELECT ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2)::NUMERIC, 0) AS prix_m2_median,
       COUNT(*) AS nb_transactions
FROM transactions t
JOIN communes_stats c ON t.commune_code = c.commune_code
JOIN dpe d ON t.commune_code = d.commune_code AND t.adresse_normalisee = d.adresse_normalisee
WHERE translate(lower(c.nom_commune), 'âàäéèêëîïôöûüùç', 'aaaeeeeiioouuuc') = 'nantes'
  AND t.type_local = 'Maison'
  AND t.surface_bati >= 100
  AND d.annee_construction < 1949
  AND t.est_valide = TRUE
  AND t.prix_m2 IS NOT NULL
  AND t.date_mutation >= NOW() - INTERVAL '60 months'
```

Q: Appartement Vannes proche gare, distribution DPE
```sql
SELECT t.dpe_classe,
       COUNT(*) AS nb,
       ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2)::NUMERIC, 0) AS prix_m2_median,
       ROUND(AVG(t.dist_gare_m)::NUMERIC, 0) AS dist_gare_moy_m
FROM transactions t
JOIN communes_stats c ON t.commune_code = c.commune_code
WHERE translate(lower(c.nom_commune), 'âàäéèêëîïôöûüùç', 'aaaeeeeiioouuuc') = 'vannes'
  AND t.type_local = 'Appartement'
  AND t.est_valide = TRUE
  AND t.prix_m2 IS NOT NULL
  AND t.dist_gare_m <= 1000
  AND t.dpe_classe IS NOT NULL
  AND t.date_mutation >= NOW() - INTERVAL '24 months'
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

            # Le LLM est instruit de ne pas utiliser % dans le SQL généré
            # On exécute le SQL brut directement
            print(f"[SQL DEBUG] Tentative {attempt+1}:\n{sql}\n", flush=True)
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


def _format_results_as_context(results: list[dict], sql: str, error: str, question: str = "") -> str:
    """Formate les résultats SQL en bloc de contexte lisible pour le LLM."""
    if error and not results:
        return (
            f"⚠ Aucune donnée disponible (erreur après {3} tentatives SQL).\n"
            f"Erreur : {error}\n"
            f"Informe l'utilisateur que tu ne peux pas répondre précisément "
            f"et suggère de reformuler la question avec un nom de commune.\n"
        )

    if not results:
        return f"Aucun résultat trouvé dans la base de données pour la question : '{question}'.\n"

    cols = list(results[0].keys())
    ctx  = "=== RÉSULTATS REQUÊTE BASE IMMOBI ===\n"
    if question:
        ctx += f"Question traitée : {question}\n"
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
Réponds TOUJOURS avec ce format exact en indiquant clairement le nom de la ville en question dans le titre du Verdict et du Prix/Loyer de référence :

**🎯 Verdict à [Nom de la ville]** : [1 phrase tranchée : bon deal / marché tendu / fort levier de négo]

**📊 Prix & Loyer de référence à [Nom de la ville]**
- Médiane d'achat locale : X €/m²
- Loyer de référence (HC) : X €/m² (si question location/rendement)
- Budget d'achat estimé : X € (si surface mentionnée)
- Loyer mensuel estimé (HC) : X € (si surface mentionnée et question location/rendement)
- Rendement locatif brut estimé : X % (si question rendement)

**🔧 Leviers de négociation / Décisions**
- [Argument 1 chiffré, ex: DPE F → décote -10% soit -XXX €]
- [Argument 2 chiffré, ou explication de rentabilité/rendement si investissement/location]
- [Argument 3 si pertinent]

**✅ Action recommandée** : [1 phrase concrète et immédiate]


## FORMAT DE RÉPONSE OBLIGATOIRE (S'IL Y A PLUSIEURS VILLES À COMPARER)
Réponds TOUJOURS avec ce format exact :

**🎯 Verdict à [Ville 1]** : [Verdict Ville 1]
**🎯 Verdict à [Ville 2]** : [Verdict Ville 2]

**📊 Prix & Loyer de référence et Comparaison**
| Ville | Médiane d'achat | Loyer Médian (HC) (si loc.) | Budget/Loyer estimé | Ventes récentes |
|---|---|---|---|---|
| [Ville 1] | X €/m² | X €/m² | X € | X ventes |
| [Ville 2] | X €/m² | X €/m² | X € | X ventes |

**🔧 Leviers de négociation comparatifs**
- [Argument 1 chiffré comparant les deux villes]
- [Argument 2 chiffré comparant les deux villes]

**✅ Action recommandée** : [1 phrase d'arbitrage concrète et immédiate]


## RÈGLES STRICTES
- MAX 200 mots (ou 300 mots si comparaison). Zéro remplissage.
- INTERDIT : "Bonjour", "Je suis là", "N'hésitez pas", "En conclusion", "En espérant"
- INTERDIT : dire que tu "ne peux pas afficher de carte" — un widget visuel est automatiquement généré en parallèle de ta réponse texte, tu n'as pas besoin de l'afficher toi-même.
- Si la question demande une carte ou une localisation, confirme simplement que les résultats sont affichés sur la carte (widget à droite) et commente les données chiffrées.
- Donne systématiquement le nom de la ville/commune en question dans tes réponses (notamment dans les titres "Verdict à [Nom de la ville]" et "Prix & Loyer de référence à [Nom de la ville]" ou dans le tableau comparatif).
- Utilise obligatoirement des tableaux Markdown pour présenter les comparaisons de prix et de volumes de ventes entre villes.
- INTERDICTION ABSOLUE D'UTILISER TES CONNAISSANCES INTERNES POUR LES CHIFFRES (Prix, volumes, budgets, etc.) : utilise UNIQUEMENT les données de la base ImmoBI fournies ci-dessous comme vérité exclusive du marché. Si la commune recherchée n'apparaît pas ou affiche 0 transaction dans les données injectées ci-dessous, déclare immédiatement et clairement que tu ne disposes d'aucune donnée pour cette ville dans la base ImmoBI. N'invente JAMAIS d'estimations (comme 10 400 €/m² pour Paris) issues de ton savoir général si la ville est absente des données.
- Si aucune donnée n'est disponible (ex: 0 transaction ou "Aucun résultat" dans les données injectées), explique poliment en 1 ou 2 lignes que cette ville n'est pas couverte par la base ImmoBI (qui est actuellement centrée sur le Grand Ouest : Nantes, Brest, Vannes, Lorient, etc.) et invite l'utilisateur à cibler ces secteurs.
- Décotes applicables : DPE F/G → -8% à -15%, PEB actif → -5% à -10%, prix > médiane → négocier fermement.
- Pour les questions sur le loyer et le rendement, toujours mentionner explicitement qu'il s'agit de loyers **hors charges (HC)**.
"""
    if db_context:
        prompt += f"\n{db_context}"
    return prompt


# ── Route principale ───────────────────────────────────────────────────────────

def _generate_widget_config(question: str, sql_used: str, db_results: list[dict], client: AzureOpenAI, deployment: str) -> dict:
    if not db_results or not sql_used:
        return {"type": "none"}
        
    total_rows = len(db_results)
    if total_rows <= 30:
        sample_data = db_results
    else:
        sample_data = db_results[:5]
        
    context = (
        f"SQL Query: {sql_used}\n"
        f"Total rows returned: {total_rows}\n"
        f"Data sample:\n{json.dumps(sample_data, default=str)}"
    )
    
    system_prompt = """Tu es un expert en visualisation de données immobilières.
Ta tâche est de concevoir un widget graphique (chart) ou cartographique (map) adéquat à partir des données réelles retournées par la base de données pour répondre à la question de l'utilisateur.

Tu dois impérativement renvoyer un objet JSON strict au format suivant (sans balise ```json, sans texte autour) :
{
  "type": "chart" | "map" | "none",
  "title": "Titre du widget visuel",
  "chart_config": {
    "type": "bar" | "line" | "pie" | "doughnut",
    "labels": ["Label1", "Label2", ...],
    "datasets": [
      {
        "label": "Nom de la série",
        "data": [valeur1, valeur2, ...]
      }
    ]
  },
  "map_config": {
    "center": [latitude, longitude],
    "zoom": 13,
    "poi_markers": [
      {"lat": latitude, "lng": longitude, "popup": "Nom du POI de référence", "type": "type_du_poi_si_connu"}
    ]
  }
}

IMPORTANT POUR LA CARTE :
Dans "map_config.poi_markers", n'inclure que les points de repère très spécifiques/uniques (par exemple, le centre de la commune ou un ou plusieurs POI de référence uniques autour desquels on cherche).
- Si la question implique une recherche de proximité ou de distance autour de points de repère (ex: "à 20 min à pied de X", "à moins de 2km de Y"), tu DOIS impérativement inclure ces points de repère dans "poi_markers" pour qu'ils soient positionnés sur la carte. Ne les laisse pas de côté.
- Si l'utilisateur cherche autour de plusieurs points de repère (ex: "un Fitness Park ou un Basic Fit", "la gare ou l'université"), tu DOIS inclure CHAQUE point de repère de manière distincte dans le tableau "poi_markers" (ex: un marker pour Fitness Park et un marker séparé pour Basic-Fit). Ne les fusionne JAMAIS en un seul marker textuel fictif comme "Fitness Park ou Basic Fit".
- "type" doit être le type de ce point d'intérêt s'il est connu (ex: 'salle_sport', 'gare', 'ecole', 'universite', 'cinema', 'restaurant', 'pharmacie', 'commerce', 'transport', 'parking'). Cela permet d'afficher l'émoticône appropriée.
- Si le point de repère de référence est une gare ferroviaire (ex: gare de Vannes, gare de Chantenay), son type dans "poi_markers" doit être impérativement "gare" (pour afficher l'icône de train 🚂) et non "transport" (qui correspond aux bus 🚌).
- Ne JAMAIS lister tous les points retournés par la requête SQL dans "poi_markers" car le serveur s'occupe de les ajouter automatiquement sur la carte via une post-analyse. Laisse "poi_markers" vide ([]) par défaut si la question ne demande pas d'afficher un repère précis en plus des biens/POIs.

Règles de décision visuelle :
1. Si l'utilisateur demande une évolution temporelle (ex: prix par trimestre, par année) -> "type": "chart" avec "chart_config.type": "line".
2. Si l'utilisateur demande une comparaison de volumes, de prix moyens, ou de prix médians entre plusieurs groupes -> "type": "chart" avec "chart_config.type": "bar".
3. Si l'utilisateur demande une répartition de parts ou de pourcentages (ex: répartition par DPE, par type local) -> "type": "chart" avec "chart_config.type": "doughnut" ou "pie".
4. Si la question demande explicitement une carte ou des localisations géographiques (ou si les données contiennent des latitudes/longitudes et que l'utilisateur veut voir où ils se situent) -> "type": "map". Laisse le centre de la carte à [47.218371, -1.553621] par défaut (Nantes) ou calcule le centre moyen à partir des coordonnées des résultats si tu le peux.
5. S'il n'y a pas d'intérêt visuel clair ou pas assez de données -> "type": "none".
"""

    try:
        resp = _call_llm_sync(
            client,
            deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context data:\n{context}\n\nUser Question: {question}"}
            ],
            max_tokens=1000,
            temperature=0.0
        )
        raw_json = resp.choices[0].message.content or ""
        raw_json = raw_json.strip()
        if raw_json.startswith("```json"):
            raw_json = raw_json[7:]
        elif raw_json.startswith("```"):
            raw_json = raw_json[3:]
        if raw_json.endswith("```"):
            raw_json = raw_json[:-3]
        raw_json = raw_json.strip()
        
        parsed = json.loads(raw_json)
        
        if parsed.get("type") == "map":
            markers = []
            seen = set()
            for row in db_results:
                if row.get("latitude") and row.get("longitude"):
                    nom = row.get("nom")
                    poi_type = row.get("type")
                    
                    # Exclure les POIs sans nom, mais conserver les transactions (qui n'ont pas de type POI ou pas de nom)
                    is_poi = poi_type is not None
                    if is_poi and (not nom or not nom.strip()):
                        continue
                        
                    key = (round(float(row["latitude"]), 5), round(float(row["longitude"]), 5))
                    if key in seen:
                        continue
                    seen.add(key)
                    details = []
                    if row.get("prix_m2"):
                        details.append(f"{row['prix_m2']} €/m²")
                    if row.get("surface_bati"):
                        details.append(f"{row['surface_bati']} m²")
                    if row.get("dpe_classe"):
                        details.append(f"DPE: {row['dpe_classe']}")
                    if row.get("valeur_fonciere"):
                        details.append(f"Valeur: {row['valeur_fonciere']} €")
                    
                    popup_details = " | ".join(details)
                    type_loc = row.get("type_local", "Bien")
                    title_info = row.get("nom") or row.get("adresse") or row.get("adresse_normalisee") or type_loc
                    popup = f"<b>{title_info}</b><br>{popup_details}"
                    markers.append({
                        "lat": float(row["latitude"]),
                        "lng": float(row["longitude"]),
                        "popup": popup,
                        "type": poi_type,
                        "valeur_fonciere": float(row["valeur_fonciere"]) if row.get("valeur_fonciere") is not None else None,
                        "prix_m2": float(row["prix_m2"]) if row.get("prix_m2") is not None else None,
                        "dpe_classe": row.get("dpe_classe"),
                        "surface_bati": float(row["surface_bati"]) if row.get("surface_bati") is not None else None,
                        "type_local": type_loc,
                        "adresse": row.get("adresse") or row.get("adresse_normalisee")
                    })
            if "map_config" not in parsed:
                parsed["map_config"] = {}
            parsed["map_config"]["markers"] = markers
            
            # Corriger les coordonnées des poi_markers à partir de la base de données (points_interet) pour éviter toute hallucination de localisation
            if "map_config" in parsed and "poi_markers" in parsed["map_config"] and parsed["map_config"]["poi_markers"]:
                # Calculer le centre des transactions pour orienter la recherche
                valid_coords = [
                    (float(m["lat"]), float(m["lng"])) for m in markers if m.get("lat") and m.get("lng")
                ]
                center_lat, center_lng = None, None
                if valid_coords:
                    center_lat = sum(c[0] for c in valid_coords) / len(valid_coords)
                    center_lng = sum(c[1] for c in valid_coords) / len(valid_coords)

                corrected_poi_markers = []

                def _dist(lat1, lon1, lat2, lon2):
                    import math
                    R = 6371.0
                    dlat = math.radians(lat2 - lat1)
                    dlon = math.radians(lon2 - lon1)
                    a = (math.sin(dlat / 2) ** 2 +
                         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
                    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                    return R * c * 1000.0

                for marker in parsed["map_config"]["poi_markers"]:
                    poi_type = marker.get("type")
                    poi_name = marker.get("popup") or ""
                    
                    # Nettoyage du nom pour la recherche
                    clean_name = poi_name.lower()
                    if poi_type == "gare":
                        # Pour les gares, on cherche le nom de la ville
                        # ex: "Gare de Vannes" -> "vannes"
                        clean_name = clean_name.replace("la gare de ", "").replace("gare de ", "").replace("gare d'", "").replace("gare de la ", "")
                        clean_name = clean_name.strip()
                    elif poi_type == "salle_sport":
                        if "fitness" in clean_name or "park" in clean_name:
                            clean_name = "fitness park"
                        elif "basic" in clean_name or "fit" in clean_name:
                            clean_name = "basic fit"
                        else:
                            for c in ["vannes", "nantes", "reze", "lorient", "brest", "hennebont", "bouvron"]:
                                clean_name = clean_name.replace(f" de {c}", "").replace(f" d'{c}", "").replace(f" à {c}", "").replace(f" {c}", "")
                            clean_name = clean_name.strip()
                    else:
                        for c in ["vannes", "nantes", "reze", "lorient", "brest", "hennebont", "bouvron"]:
                            clean_name = clean_name.replace(f" de {c}", "").replace(f" d'{c}", "").replace(f" à {c}", "").replace(f" {c}", "")
                        clean_name = clean_name.strip()
                    
                    if clean_name:
                        # Récupérer tous les POIs du type et nom correspondants
                        sql_lookup = """
                            SELECT latitude, longitude, nom, type
                            FROM points_interet
                            WHERE (type = %s OR %s IS NULL)
                              AND (
                                replace(replace(lower(COALESCE(nom,'')), '-', ''), ' ', '') = %s
                                OR lower(nom) LIKE %s
                              )
                        """
                        norm_name = clean_name.replace(" ", "").replace("-", "")
                        db_pois = query(sql_lookup, (poi_type, poi_type, norm_name, f"%{clean_name}%"))
                        
                        if db_pois:
                            matched_any = False
                            if valid_coords:
                                # Associer tous les POIs qui sont à moins de 2km d'au moins une transaction
                                for poi in db_pois:
                                    poi_lat = float(poi["latitude"])
                                    poi_lng = float(poi["longitude"])
                                    if any(_dist(poi_lat, poi_lng, tx_lat, tx_lng) <= 2000 for tx_lat, tx_lng in valid_coords):
                                        corrected_poi_markers.append({
                                            "lat": poi_lat,
                                            "lng": poi_lng,
                                            "popup": poi["nom"] or poi_name,
                                            "type": poi["type"] or poi_type
                                        })
                                        matched_any = True
                            
                            # Fallback si aucun POI n'est à moins de 2km d'une transaction, ou si pas de transactions
                            if not matched_any:
                                if center_lat is not None and center_lng is not None:
                                    sql_closest = """
                                        SELECT latitude, longitude, nom, type
                                        FROM points_interet
                                        WHERE (type = %s OR %s IS NULL)
                                          AND (
                                            replace(replace(lower(COALESCE(nom,'')), '-', ''), ' ', '') = %s
                                            OR lower(nom) LIKE %s
                                          )
                                        ORDER BY 
                                          geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                                          id LIMIT 1
                                    """
                                    db_pois_closest = query(sql_closest, (poi_type, poi_type, norm_name, f"%{clean_name}%", center_lng, center_lat))
                                else:
                                    sql_closest = """
                                        SELECT latitude, longitude, nom, type
                                        FROM points_interet
                                        WHERE (type = %s OR %s IS NULL)
                                          AND (
                                            replace(replace(lower(COALESCE(nom,'')), '-', ''), ' ', '') = %s
                                            OR lower(nom) LIKE %s
                                          )
                                        ORDER BY 
                                          CASE WHEN replace(replace(lower(COALESCE(nom,'')), '-', ''), ' ', '') = %s THEN 0 ELSE 1 END,
                                          id LIMIT 1
                                    """
                                    db_pois_closest = query(sql_closest, (poi_type, poi_type, norm_name, f"%{clean_name}%", norm_name))
                                
                                if db_pois_closest:
                                    corrected_poi_markers.append({
                                        "lat": float(db_pois_closest[0]["latitude"]),
                                        "lng": float(db_pois_closest[0]["longitude"]),
                                        "popup": db_pois_closest[0]["nom"] or poi_name,
                                        "type": db_pois_closest[0]["type"] or poi_type
                                    })
                
                # Dédupliquer les marqueurs
                seen_markers = set()
                dedup_poi_markers = []
                for m in corrected_poi_markers:
                    key = (round(m["lat"], 5), round(m["lng"], 5))
                    if key not in seen_markers:
                        seen_markers.add(key)
                        dedup_poi_markers.append(m)
                
                parsed["map_config"]["poi_markers"] = dedup_poi_markers

            if markers:
                avg_lat = sum(m["lat"] for m in markers) / len(markers)
                avg_lng = sum(m["lng"] for m in markers) / len(markers)
                parsed["map_config"]["center"] = [avg_lat, avg_lng]
                
        return parsed
    except Exception as e:
        log.error("Error creating widget config in chat backend: %s", e)
        return {"type": "none"}

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
    db_context    = _format_results_as_context(db_results, sql_used, sql_error, latest)
    system_prompt = _build_system_prompt(db_context)
    api_messages  = [{"role": "system", "content": system_prompt}] + messages

    widget_config = _generate_widget_config(latest, sql_used, db_results, client, deployment)

    # ── Phase 2 : Réponse en streaming ────────────────────────────────────────
    def generate():
        try:
            yield f"data: {json.dumps({'widget': widget_config})}\n\n"
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
