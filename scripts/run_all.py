"""
Script maître — lance tous les chargements dans l'ordre correct.
Lance : python scripts/run_all.py

Ordre :
  1. Communes        (~10 min)
  2. DVF 2021-2025   (~2h15)
  3. DPE             (~2h15)
  4. POI             (~20 min)
  5. Filosofi INSEE  (~5 min)
  6. Enrichissement  (~15 min)

Durée totale estimée : ~5h30

Options :
  python scripts/run_all.py --only communes dvf
  python scripts/run_all.py --skip dpe
"""
import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("run_all")

ETAPES_ORDRE = ["communes", "dvf", "dpe", "peb", "poi", "filosofi", "enrichissement", "quality"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", choices=ETAPES_ORDRE,
                        help="Lancer uniquement ces étapes")
    parser.add_argument("--skip", nargs="*", choices=ETAPES_ORDRE,
                        help="Sauter ces étapes")
    args = parser.parse_args()

    skip = set(args.skip or [])
    only = set(args.only or ETAPES_ORDRE)
    a_lancer = [e for e in ETAPES_ORDRE if e in only and e not in skip]

    log.info("╔══════════════════════════════════════════════════════╗")
    log.info("║  RUN ALL — Bretagne + Pays de la Loire 2021-2025    ║")
    log.info("╠══════════════════════════════════════════════════════╣")
    log.info("║  Étapes : %-42s ║", " → ".join(a_lancer))
    log.info("╚══════════════════════════════════════════════════════╝")
    print()

    t0 = time.time()
    resultats = {}

    for etape in a_lancer:
        log.info("▶ Démarrage étape : %s", etape.upper())
        t_etape = time.time()
        try:
            if etape == "communes":
                from scripts.load_communes import main as run
            elif etape == "dvf":
                from scripts.load_dvf import main as run
            elif etape == "dpe":
                from scripts.load_dpe import main as run
            elif etape == "peb":
                from scripts.load_peb import main as run
            elif etape == "poi":
                from scripts.load_poi import main as run
            elif etape == "filosofi":
                from scripts.load_filosofi import main as run
            elif etape == "enrichissement":
                from scripts.load_enrichment import main as run
            elif etape == "quality":
                from scripts.load_quality import main as run

            run()
            duree = time.time() - t_etape
            resultats[etape] = f"✓ {duree/60:.1f} min"
            log.info("✓ %s terminé en %.1f min", etape.upper(), duree / 60)
        except Exception as e:
            duree = time.time() - t_etape
            resultats[etape] = f"✗ ERREUR après {duree/60:.1f} min"
            log.error("✗ %s ERREUR : %s", etape.upper(), e)
            log.exception(e)
        print()

    total = time.time() - t0
    log.info("╔══════════════════════════════════════════════════════╗")
    log.info("║                   BILAN FINAL                       ║")
    log.info("╠══════════════════════════════════════════════════════╣")
    for etape, statut in resultats.items():
        log.info("║  %-15s %s%-35s ║", etape, "", statut)
    log.info("╠══════════════════════════════════════════════════════╣")
    log.info("║  Durée totale : %-37s ║", f"{total/3600:.1f}h ({total/60:.0f} min)")
    log.info("╚══════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
