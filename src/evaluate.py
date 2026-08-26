"""
Porte de qualité du modèle.

Ce script est ce qui donne à la chaîne d'intégration le droit de dire non.
Il relit les métriques produites par l'entraînement et les compare aux seuils
de params.yaml. S'il sort en code 1, la pull request ne peut pas être fusionnée.

Usage :
    python -m src.evaluate
"""

import json
import pathlib
import sys

import yaml

from src import journal

RACINE = pathlib.Path(__file__).resolve().parents[1]


def evaluer() -> int:
    log = journal.configurer("evaluate")
    journal.demarrer(log, "porte de qualité")

    with open(RACINE / "params.yaml", encoding="utf-8") as f:
        params = yaml.safe_load(f)

    chemin = RACINE / "reports" / "metriques.json"
    if not chemin.exists():
        journal.dire(log, "ÉCHEC : aucune métrique trouvée. Lancez d'abord python -m src.train")
        return 1

    with open(chemin, encoding="utf-8") as f:
        m = json.load(f)

    seuils = {
        "f1": params["evaluation"]["seuil_f1"],
        "rappel": params["evaluation"]["seuil_rappel"],
    }

    journal.dire(log, f"Modèle {m['version_modele']} — seuil de décision {m['seuil_decision']}")
    journal.dire(log, f"{'métrique':<12}{'obtenu':>10}{'exigé':>10}   verdict")
    journal.dire(log, "-" * 46)

    echecs = []
    for nom, exige in seuils.items():
        obtenu = m[nom]
        ok = obtenu >= exige
        journal.dire(log, f"{nom:<12}{obtenu:>10.4f}{exige:>10.4f}   {'OK' if ok else 'ÉCHEC'}")
        if not ok:
            echecs.append((nom, obtenu, exige))

    journal.dire(log, "-" * 46)
    if echecs:
        for nom, obtenu, exige in echecs:
            journal.dire(log,
                f"ÉCHEC : le seuil « {nom} » n'est pas tenu — "
                f"{obtenu:.4f} obtenu, {exige:.4f} exigé."
            )
        journal.dire(log, "La fusion est refusée. Corrigez le modèle ou justifiez le seuil.")
        return 1

    journal.dire(log, "Tous les seuils sont tenus. La fusion est autorisée.")
    return 0


if __name__ == "__main__":
    sys.exit(evaluer())
