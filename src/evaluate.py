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

RACINE = pathlib.Path(__file__).resolve().parents[1]


def evaluer() -> int:
    with open(RACINE / "params.yaml", encoding="utf-8") as f:
        params = yaml.safe_load(f)

    chemin = RACINE / "reports" / "metriques.json"
    if not chemin.exists():
        print("ÉCHEC : aucune métrique trouvée. Lancez d'abord python -m src.train")
        return 1

    with open(chemin, encoding="utf-8") as f:
        m = json.load(f)

    seuils = {
        "f1": params["evaluation"]["seuil_f1"],
        "rappel": params["evaluation"]["seuil_rappel"],
    }

    print(f"Modèle {m['version_modele']} — seuil de décision {m['seuil_decision']}")
    print(f"{'métrique':<12}{'obtenu':>10}{'exigé':>10}   verdict")
    print("-" * 46)

    echecs = []
    for nom, exige in seuils.items():
        obtenu = m[nom]
        ok = obtenu >= exige
        print(f"{nom:<12}{obtenu:>10.4f}{exige:>10.4f}   {'OK' if ok else 'ÉCHEC'}")
        if not ok:
            echecs.append((nom, obtenu, exige))

    print("-" * 46)
    if echecs:
        for nom, obtenu, exige in echecs:
            print(
                f"ÉCHEC : le seuil « {nom} » n'est pas tenu — "
                f"{obtenu:.4f} obtenu, {exige:.4f} exigé."
            )
        print("La fusion est refusée. Corrigez le modèle ou justifiez le seuil.")
        return 1

    print("Tous les seuils sont tenus. La fusion est autorisée.")
    return 0


if __name__ == "__main__":
    sys.exit(evaluer())
