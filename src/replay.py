"""
Rejoue du trafic contre le service de prédiction.

Atelier 2 : générer du trafic normal pour voir le tableau de bord se remplir.
    python -m src.replay --n 500

Atelier 3 : rejouer le trafic dérivé de 2026.
    python -m src.replay --input data/drifted_2026.csv --n 800

Le script écrit aussi les prédictions dans reports/predictions.csv, ce qui
permet à src.drift_report de comparer les distributions de scores.
"""

import argparse
import pathlib
import sys
import time

import pandas as pd
import requests

RACINE = pathlib.Path(__file__).resolve().parents[1]
COLONNES = [
    "montant",
    "heure",
    "frequence_7j",
    "anciennete_jours",
    "type_contrepartie",
]


def rejouer(chemin: str, n: int, url: str, pause: float) -> pd.DataFrame:
    df = pd.read_csv(RACINE / chemin)
    if n and n < len(df):
        df = df.sample(n=n, random_state=7).reset_index(drop=True)

    lignes, erreurs = [], 0
    debut = time.time()

    for i, ligne in df.iterrows():
        charge = {c: ligne[c] for c in COLONNES}
        charge["montant"] = float(charge["montant"])
        for c in ("heure", "frequence_7j", "anciennete_jours"):
            charge[c] = int(charge[c])
        try:
            r = requests.post(f"{url}/predict", json=charge, timeout=5)
            r.raise_for_status()
            reponse = r.json()
            lignes.append({**charge, "score": reponse["score"],
                           "signalee": reponse["signalee"]})
        except Exception as exc:  # noqa: BLE001
            erreurs += 1
            if erreurs <= 3:
                print(f"  erreur sur la requête {i} : {exc}", file=sys.stderr)
        if pause:
            time.sleep(pause)
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(df)} requêtes envoyées")

    duree = time.time() - debut
    resultat = pd.DataFrame(lignes)

    print(f"\n{len(resultat)} prédictions en {duree:.1f} s "
          f"({len(resultat) / max(duree, 0.01):.0f} req/s)")
    if erreurs:
        print(f"{erreurs} requêtes en erreur")
    if not resultat.empty:
        print(f"score moyen        : {resultat.score.mean():.4f}")
        print(f"taux de signalement: {resultat.signalee.mean():.2%}")

    return resultat


def principal():
    ap = argparse.ArgumentParser(description="Rejoue du trafic contre l'API.")
    ap.add_argument("--input", default="data/reference_2025.csv",
                    help="fichier de trafic à rejouer")
    ap.add_argument("--n", type=int, default=500, help="nombre de requêtes")
    ap.add_argument("--url", default="http://localhost:8000", help="adresse du service")
    ap.add_argument("--pause", type=float, default=0.0,
                    help="pause entre deux requêtes, en secondes")
    ap.add_argument("--sortie", default="reports/predictions.csv")
    args = ap.parse_args()

    print(f"Rejeu de {args.input} vers {args.url}")
    resultat = rejouer(args.input, args.n, args.url, args.pause)

    if not resultat.empty:
        (RACINE / "reports").mkdir(exist_ok=True)
        chemin = RACINE / args.sortie
        resultat.to_csv(chemin, index=False)
        print(f"Prédictions écrites dans {args.sortie}")


if __name__ == "__main__":
    principal()
