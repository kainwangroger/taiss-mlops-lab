"""
Rapport de dérive.

Compare un jeu courant à la fenêtre de référence figée et produit un rapport
HTML autoportant. Trois tests, selon la nature de la variable :

  - Indice de stabilité (PSI) sur les variables continues, binnées sur les
    déciles de la référence. Lecture : < 0,10 stable · 0,10–0,25 à surveiller ·
    > 0,25 dérive avérée.
  - Kolmogorov–Smirnov sur les variables continues, pour confirmer.
  - Khi-deux sur les variables catégorielles, avec détection des catégories
    nouvelles — celles qui n'existaient pas à l'entraînement.

Le rapport est calculé sans dépendance externe autre que numpy, pandas et
scipy. C'est un choix délibéré : un lab de deux heures ne peut pas dépendre
d'une bibliothèque dont l'API change entre versions majeures.

Usage :
    python -m src.drift_report
    python -m src.drift_report --courant data/drifted_2026.csv
"""

import argparse
import datetime
import html
import pathlib

import numpy as np
import pandas as pd
import yaml
from scipy import stats

from src import journal
from src.features import COLONNES_CATEGORIELLES, COLONNES_NUMERIQUES

RACINE = pathlib.Path(__file__).resolve().parents[1]


def psi(reference: pd.Series, courant: pd.Series, n_bins: int = 10) -> float:
    """Population Stability Index, binné sur les quantiles de la référence."""
    bornes = np.unique(np.quantile(reference, np.linspace(0, 1, n_bins + 1)))
    if len(bornes) < 3:
        return 0.0
    bornes[0], bornes[-1] = -np.inf, np.inf

    ref_pct = np.histogram(reference, bins=bornes)[0] / len(reference)
    cou_pct = np.histogram(courant, bins=bornes)[0] / len(courant)

    # Lissage pour éviter les divisions par zéro sur les bacs vides.
    eps = 1e-6
    ref_pct = np.clip(ref_pct, eps, None)
    cou_pct = np.clip(cou_pct, eps, None)

    return float(np.sum((cou_pct - ref_pct) * np.log(cou_pct / ref_pct)))


def verdict(valeur: float, params: dict) -> str:
    if valeur >= params["derive"]["psi_alerte"]:
        return "DÉRIVE AVÉRÉE"
    if valeur >= params["derive"]["psi_surveillance"]:
        return "À SURVEILLER"
    return "STABLE"


def analyser(ref: pd.DataFrame, cou: pd.DataFrame, params: dict) -> list:
    resultats = []

    for col in COLONNES_NUMERIQUES:
        if col not in ref or col not in cou:
            continue
        valeur_psi = psi(ref[col], cou[col])
        ks = stats.ks_2samp(ref[col], cou[col])
        resultats.append({
            "variable": col,
            "type": "numérique",
            "psi": valeur_psi,
            "test": "Kolmogorov–Smirnov",
            "p_value": float(ks.pvalue),
            "detail": (f"médiane {ref[col].median():,.0f} → {cou[col].median():,.0f}"),
            "verdict": verdict(valeur_psi, params),
            "nouveau": "",
        })

    for col in COLONNES_CATEGORIELLES:
        if col not in ref or col not in cou:
            continue
        cats_ref = set(ref[col].unique())
        cats_cou = set(cou[col].unique())
        nouvelles = sorted(cats_cou - cats_ref)

        toutes = sorted(cats_ref | cats_cou)
        p_ref = np.array([(ref[col] == c).mean() for c in toutes])
        p_cou = np.array([(cou[col] == c).mean() for c in toutes])
        eps = 1e-6
        valeur_psi = float(np.sum((np.clip(p_cou, eps, None) - np.clip(p_ref, eps, None))
                                  * np.log(np.clip(p_cou, eps, None) / np.clip(p_ref, eps, None))))

        obs = np.array([(cou[col] == c).sum() for c in toutes])
        att = np.clip(p_ref * len(cou), 1e-6, None)
        chi2 = float(np.sum((obs - att) ** 2 / att))
        ddl = max(len(toutes) - 1, 1)
        p_value = float(1 - stats.chi2.cdf(chi2, ddl))

        resultats.append({
            "variable": col,
            "type": "catégoriel",
            "psi": valeur_psi,
            "test": "Khi-deux",
            "p_value": p_value,
            "detail": f"{len(cats_ref)} catégories connues, {len(cats_cou)} observées",
            "verdict": "DÉRIVE AVÉRÉE" if nouvelles else verdict(valeur_psi, params),
            "nouveau": ", ".join(nouvelles),
        })

    return sorted(resultats, key=lambda r: r["psi"], reverse=True)


COULEURS = {
    "DÉRIVE AVÉRÉE": "#C8102E",
    "À SURVEILLER": "#C8871B",
    "STABLE": "#17795E",
}


def rendre_html(resultats: list, ref: pd.DataFrame, cou: pd.DataFrame,
                nom_ref: str, nom_cou: str) -> str:
    horodatage = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    lignes = []
    for r in resultats:
        alerte = ""
        if r["nouveau"]:
            alerte = (f"<div class='alerte'>Catégorie absente du jeu "
                      f"d'entraînement : <b>{html.escape(r['nouveau'])}</b></div>")
        lignes.append(f"""
        <tr>
          <td><b>{html.escape(r['variable'])}</b><div class='muted'>{r['type']}</div></td>
          <td class='num'>{r['psi']:.3f}</td>
          <td class='num'>{r['p_value']:.2e}<div class='muted'>{html.escape(r['test'])}</div></td>
          <td>{html.escape(r['detail'])}{alerte}</td>
          <td><span class='badge' style='background:{COULEURS[r["verdict"]]}'>{r['verdict']}</span></td>
        </tr>""")

    n_derive = sum(1 for r in resultats if r["verdict"] == "DÉRIVE AVÉRÉE")

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>Rapport de dérive — {html.escape(nom_cou)}</title>
<style>
 body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
        margin: 0; padding: 40px; background: #F7FAF8; color: #12211C; }}
 .wrap {{ max-width: 980px; margin: 0 auto; }}
 h1 {{ color: #0C4B33; margin: 0 0 4px; font-size: 28px; }}
 .sous {{ color: #6B7F76; margin-bottom: 28px; }}
 .cartes {{ display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }}
 .carte {{ background: #fff; border: 1px solid #E1EDE7; border-radius: 10px;
          padding: 16px 20px; flex: 1; min-width: 180px; }}
 .carte .k {{ color: #6B7F76; font-size: 12px; text-transform: uppercase;
             letter-spacing: 1px; }}
 .carte .v {{ font-size: 26px; font-weight: 700; color: #0C4B33; margin-top: 4px; }}
 table {{ width: 100%; border-collapse: collapse; background: #fff;
         border: 1px solid #E1EDE7; border-radius: 10px; overflow: hidden; }}
 th {{ background: #0C4B33; color: #fff; text-align: left; padding: 12px 14px;
      font-size: 13px; }}
 td {{ padding: 12px 14px; border-top: 1px solid #EDF4F0; vertical-align: top;
      font-size: 14px; }}
 td.num {{ font-variant-numeric: tabular-nums; }}
 .muted {{ color: #6B7F76; font-size: 12px; margin-top: 2px; }}
 .badge {{ color: #fff; padding: 4px 10px; border-radius: 12px; font-size: 12px;
          font-weight: 600; white-space: nowrap; }}
 .alerte {{ margin-top: 6px; padding: 6px 10px; background: #FBEEEC;
           border-left: 3px solid #C8102E; font-size: 13px; }}
 .note {{ margin-top: 28px; padding: 16px 20px; background: #E8F1EC;
         border-radius: 10px; font-size: 14px; line-height: 1.55; }}
</style></head><body><div class="wrap">
<h1>Rapport de dérive</h1>
<div class="sous">Référence : {html.escape(nom_ref)} ({len(ref):,} lignes) &nbsp;·&nbsp;
  Courant : {html.escape(nom_cou)} ({len(cou):,} lignes) &nbsp;·&nbsp; {horodatage}</div>

<div class="cartes">
  <div class="carte"><div class="k">Variables analysées</div><div class="v">{len(resultats)}</div></div>
  <div class="carte"><div class="k">En dérive avérée</div><div class="v">{n_derive}</div></div>
  <div class="carte"><div class="k">Seuil d'alerte PSI</div><div class="v">0,25</div></div>
</div>

<table>
<tr><th>Variable</th><th>PSI</th><th>p-value</th><th>Détail</th><th>Verdict</th></tr>
{''.join(lignes)}
</table>

<div class="note">
<b>Comment lire ce rapport.</b> Le PSI mesure l'écart entre la distribution de
référence et la distribution courante : en dessous de 0,10 la variable est
stable, entre 0,10 et 0,25 elle mérite d'être surveillée, au-dessus de 0,25 la
dérive est avérée. La p-value confirme statistiquement l'écart, mais attention :
sur de gros volumes, tout devient significatif. Le PSI reste le plus lisible.
<br><br>
<b>Et maintenant ?</b> Un PSI élevé ne dit pas quoi faire. Avant de réentraîner,
posez-vous trois questions : la dérive touche-t-elle tout le trafic ou seulement
un segment ? S'agit-il d'un changement de profil des entrées, ou d'un changement
de la relation entre les entrées et la fraude ? Et vos données récentes
sont-elles étiquetées de façon fiable, ou faut-il attendre la vérification des
analystes ? Réentraîner sur des données dont la relation a changé, sans
comprendre pourquoi, produit un modèle qui se trompe autrement.
</div>
</div></body></html>"""


def principal():
    log = journal.configurer("derive")
    ap = argparse.ArgumentParser(description="Produit un rapport de dérive.")
    ap.add_argument("--reference", default=None)
    ap.add_argument("--courant", default=None)
    ap.add_argument("--sortie", default="reports/derive.html")
    args = ap.parse_args()

    with open(RACINE / "params.yaml", encoding="utf-8") as f:
        params = yaml.safe_load(f)

    nom_ref = args.reference or params["donnees"]["reference"]
    nom_cou = args.courant or params["donnees"]["derive"]

    ref = pd.read_csv(RACINE / nom_ref)
    cou = pd.read_csv(RACINE / nom_cou)

    resultats = analyser(ref, cou, params)

    journal.dire(log, f"{'variable':<22}{'PSI':>8}   verdict")
    journal.dire(log, "-" * 56)
    for r in resultats:
        marque = f"  ← nouvelle catégorie : {r['nouveau']}" if r["nouveau"] else ""
        journal.dire(log, f"{r['variable']:<22}{r['psi']:>8.3f}   {r['verdict']}{marque}")

    (RACINE / "reports").mkdir(exist_ok=True)
    chemin = RACINE / args.sortie
    chemin.write_text(rendre_html(resultats, ref, cou, nom_ref, nom_cou), encoding="utf-8")
    journal.dire(log, f"\nRapport écrit dans {args.sortie} — ouvrez-le dans votre navigateur.")


if __name__ == "__main__":
    principal()
