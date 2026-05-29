"""
Configuration partagée par tous les scripts d'ingestion.
Modifier ici les départements et années cibles.
"""
FORCE_OVERWRITE = False

DEPARTEMENTS = [
    # Bretagne
    # "22",  # Côtes-d'Armor
    # "29",  # Finistère
    # "35",  # Ille-et-Vilaine
    # "56",  # Morbihan
    # Pays de la Loire
    "44",  # Loire-Atlantique
    # "49",  # Maine-et-Loire
    # "53",  # Mayenne
    # "72",  # Sarthe
    # "85",  # Vendée
]

ANNEES = [2021, 2022, 2023, 2024, 2025]

# Bounding boxes (lat_min, lon_min, lat_max, lon_max) pour Overpass API
BBOXES = {
    "22": (48.00, -3.70, 48.90, -1.50),
    "29": (47.73, -5.16, 48.80, -3.31),
    "35": (47.63, -2.01, 48.72, -0.92),
    "44": (46.88, -2.56, 47.83, -1.04),
    "49": (46.90, -1.60, 47.80,  0.10),
    "53": (47.60, -1.20, 48.60,  0.40),
    "56": (47.30, -3.70, 48.20, -1.80),
    "72": (47.60, -0.40, 48.80,  0.80),
    "85": (46.20, -2.40, 47.20, -0.60),
}

DSN = None  # Chargé depuis .env automatiquement
