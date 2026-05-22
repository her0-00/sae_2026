# 🚀 État Actuel du Projet — ImmoBI 2026

Ce document résume l'architecture actuelle du projet, les fonctionnalités implémentées, ainsi que l'intégration récente de l'outil d'exploration de base de données.

---

## 1. ⚙️ Pipeline de Données (ETL/ELT) (`main.py`)
Un pipeline complet en 9 étapes automatisées permet de collecter, nettoyer et croiser les données :
*   **Étape 1 — Communes** : Téléchargement et insertion des contours géographiques des communes via l'API Géo de l'IGN.
*   **Étape 2 — DVF (Transactions)** : Téléchargement, nettoyage des valeurs aberrantes (outliers), dédoublonnage et insertion par lots (batchs) des transactions immobilières.
*   **Étape 3 — DPE** : Récupération des Diagnostics de Performance Énergétique (DPE) via l'API ADEME avec pagination.
*   **Étape 4 & 5 — Gares & Écoles** : Extraction et géolocalisation des points d'intérêt via l'API Overpass d'OpenStreetMap (OSM).
*   **Étape 6 — Enrichissement DPE** : Jointure spatiale/adresse pour attribuer la classe énergétique et la consommation DPE aux transactions DVF.
*   **Étape 7 — Calculs des Distances** : Calcul spatial des distances exactes de chaque transaction par rapport à la gare et à l'école la plus proche.
*   **Étape 8 — Vues Matérialisées** : Rafraîchissement des statistiques agrégées (prix m² médian par commune, statistiques de gares, etc.).
*   **Étape 9 — Journal Qualité** : Exécution de contrôles de cohérence et archivage des résultats dans la table `quality_log`.

---

## 2. 🔌 Serveur Backend Flask (`api/`)
Une API REST modulaire et performante, structurée autour de plusieurs Blueprints :
*   **Transactions (`/api/transactions`)** : Lecture et filtrage des données DVF.
*   **Estimateur (`/api/estimateur`)** : Algorithme d'estimation de la valeur foncière en fonction des caractéristiques du bien et de sa localisation.
*   **Carte (`/api/carte`) [MIS À JOUR]** : Fourniture des données géographiques (GeoJSON) des prix au m² pour le rendu cartographique avec **calcul géométrique instantané du centroïde géographique** (`ST_Centroid`) pour chaque commune.
*   **Analyses (`/api/analyses`)** : Agrégats statistiques pour les graphiques.
*   **Opportunités (`/api/opportunites`)** : Algorithme d'identification des bonnes affaires immobilières (prix bas, revenus élevés, faible bruit).
*   **Communes (`/api/communes`)** : Moteur de recherche d'INSEE/communes.
*   **Explorateur DB (`/api/explorer`) [NOUVEAU]** : Endpoints hautement sécurisés (immunisés contre les injections SQL grâce à `psycopg2.sql`) permettant d'inspecter les tables, d'extraire les schémas, de paginer/trier les lignes de données et d'exécuter des requêtes SQL transactionnelles libres.

---

## 3. 🎨 Frontend Interactif (`frontend/`)
Une interface web monopage (SPA) moderne et épurée, connectée aux API Flask :
*   **Page d'Accueil / Estimateur (`index.html`) [MIS À JOUR]** : Formulaire interactif permettant d'estimer un bien immobilier en temps réel. Intègre désormais une **visualisation optimisée des courbes d'évolution temporelle** avec mise à l'échelle dynamique intelligente de l'axe Y et corrections de contrastes ergonomiques sur l'autocomplétion en mode sombre.
*   **Carte des Prix (`carte.html`) [MIS À JOUR]** : Carte choroplèthe interactive affichant le prix au m² médian par commune avec **bascule dynamique entre vue Plan et vue Satellite haute définition (Esri World Imagery)**, contrôle d'opacité automatisé selon la couche active, et un **bouton d'immersion satellitaire vers Google Maps** basé sur les coordonnées exactes du centroïde de la commune survolée.
*   **Analyse Commune (`commune.html`) [MIS À JOUR]** : Dossier d'analyse détaillé (population, chômage, prix médians) doté de **graphiques élargis et réactifs (Chart.js)** avec gestion automatique d'un rembourrage intelligent (padding) sur l'axe Y pour éviter le tassement des données extrêmes.
*   **Opportunités (`opportunites.html`)** : Outil de recherche multicritère des meilleures opportunités du marché.
*   **Explorateur de Base de Données (`explorer.html`) [NOUVEAU]** : 
    *   **Barre latérale** : Liste dynamique des tables avec recherche textuelle et compteurs de lignes.
    *   **Vue Données** : Tableau interactif avec pagination fluide (10, 25, 50, 100 lignes), filtres par colonne et tri instantané par clic d'en-tête.
    *   **Export CSV** : Téléchargement de la grille de données active en un clic.
    *   **Vue Structure** : Détail complet des types, nullabilité et clés primaires de la table.
    *   **Console SQL** : Éditeur SQL avec raccourci `Ctrl + Entrée` pour exécuter des requêtes en temps réel avec temps d'exécution en ms et retour d'erreur PostgreSQL détaillé en cas de faute de frappe.
