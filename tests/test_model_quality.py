"""
Étage 3 — tests de qualité du modèle.

Ces tests n'existent pas dans un projet logiciel classique. Ils décident, à
votre place et objectivement, si le modèle a le droit d'être fusionné.

Ils s'exécutent après l'entraînement : la chaîne d'intégration lance
python -m src.train avant d'appeler pytest sur ce fichier.
"""

import json
import pathlib

import joblib
import pandas as pd
import pytest
import yaml
from sklearn.metrics import f1_score

from src.features import CIBLE, construire_features

RACINE = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def params():
    with open(RACINE / "params.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def metriques():
    chemin = RACINE / "reports" / "metriques.json"
    if not chemin.exists():
        pytest.fail("reports/metriques.json est absent. Lancez : python -m src.train")
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def modele():
    chemin = RACINE / "models" / "modele.pkl"
    if not chemin.exists():
        pytest.fail("models/modele.pkl est absent. Lancez : python -m src.train")
    return joblib.load(chemin)


def test_le_f1_atteint_le_seuil(metriques, params):
    seuil = params["evaluation"]["seuil_f1"]
    obtenu = metriques["f1"]
    assert obtenu >= seuil, (
        f"seuil de qualité non tenu : F1 = {obtenu:.4f}, seuil exigé = {seuil:.4f}. "
        "Le modèle ne peut pas être promu en l'état."
    )


def test_le_rappel_atteint_le_seuil(metriques, params):
    seuil = params["evaluation"]["seuil_rappel"]
    obtenu = metriques["rappel"]
    assert obtenu >= seuil, (
        f"seuil de rappel non tenu : {obtenu:.4f} obtenu, {seuil:.4f} exigé. "
        "En détection de fraude, un rappel faible signifie des fraudes non vues."
    )


def test_le_modele_predit_les_deux_classes(modele, params):
    """Un modèle qui ne signale jamais rien a un excellent taux d'erreur global."""
    df = pd.read_csv(RACINE / params["donnees"]["reference"]).sample(
        2000, random_state=params["graine"]
    )
    proba = modele.predict_proba(construire_features(df))[:, 1]
    signalees = (proba >= params["evaluation"]["seuil_decision"]).sum()
    assert signalees > 0, "le modèle ne signale aucune transaction"
    assert signalees < len(df), "le modèle signale toutes les transactions"


def test_la_performance_tient_par_sous_population(modele, params):
    """
    Un gain global peut masquer un effondrement sur un segment.

    Ici on vérifie que le modèle tient sur chaque type de contrepartie, et pas
    seulement en moyenne. C'est le test que les équipes oublient le plus
    souvent, et celui qui révèle les biais.
    """
    df = pd.read_csv(RACINE / params["donnees"]["reference"])
    X = construire_features(df)
    proba = modele.predict_proba(X)[:, 1]
    df = df.assign(pred=(proba >= params["evaluation"]["seuil_decision"]).astype(int))

    plancher = params["evaluation"]["seuil_f1_segment"]
    faibles = {}
    for segment, groupe in df.groupby("type_contrepartie"):
        if groupe[CIBLE].sum() < 10:      # segment trop petit pour conclure
            continue
        score = f1_score(groupe[CIBLE], groupe["pred"])
        if score < plancher:
            faibles[segment] = round(float(score), 4)

    assert not faibles, (
        f"performance insuffisante sur certains segments : {faibles} "
        f"(plancher exigé : {plancher})"
    )
