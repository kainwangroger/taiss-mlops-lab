"""
Entraînement du détecteur de fraude.

Aucun paramètre en dur : tout vient de params.yaml. C'est ce qui rend
l'entraînement rejouable à l'identique et l'atelier 1 possible.

Usage :
    python -m src.train
"""

import json
import pathlib

import joblib
import pandas as pd
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src import journal, suivi
from src.features import (
    CIBLE,
    COLONNES_CATEGORIELLES,
    colonnes_numeriques_finales,
    construire_features,
)

RACINE = pathlib.Path(__file__).resolve().parents[1]


def charger_params() -> dict:
    with open(RACINE / "params.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def construire_pipeline(params: dict) -> Pipeline:
    pre = ColumnTransformer(
        transformers=[
            ("num", "passthrough", colonnes_numeriques_finales()),
            (
                "cat",
                # handle_unknown="ignore" : une catégorie inconnue ne fait pas
                # planter le service. Elle le fait juste se tromper en silence.
                # C'est exactement le comportement que l'atelier 3 met en évidence.
                OneHotEncoder(handle_unknown="ignore"),
                COLONNES_CATEGORIELLES,
            ),
        ]
    )
    modele = RandomForestClassifier(
        n_estimators=params["modele"]["n_estimators"],
        max_depth=params["modele"]["max_depth"],
        min_samples_leaf=params["modele"]["min_samples_leaf"],
        class_weight="balanced_subsample",
        random_state=params["graine"],
        n_jobs=-1,
    )
    return Pipeline([("pre", pre), ("modele", modele)])


def entrainer() -> dict:
    params = charger_params()
    df = pd.read_csv(RACINE / params["donnees"]["reference"])

    X = construire_features(df)
    y = df[CIBLE]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=params["donnees"]["part_test"],
        random_state=params["graine"],
        stratify=y,
    )

    pipeline = construire_pipeline(params)
    pipeline.fit(X_train, y_train)

    seuil = params["evaluation"]["seuil_decision"]
    y_proba = pipeline.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= seuil).astype(int)

    metriques = {
        "f1": round(float(f1_score(y_test, y_pred)), 4),
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "rappel": round(float(recall_score(y_test, y_pred)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, y_proba)), 4),
        "seuil_decision": seuil,
        "version_modele": params["version_modele"],
        "n_entrainement": int(len(X_train)),
        "n_test": int(len(X_test)),
    }

    (RACINE / "models").mkdir(exist_ok=True)
    (RACINE / "reports").mkdir(exist_ok=True)
    joblib.dump(pipeline, RACINE / "models" / "modele.pkl")
    with open(RACINE / "reports" / "metriques.json", "w", encoding="utf-8") as f:
        json.dump(metriques, f, indent=2, ensure_ascii=False)

    # Section « aller plus loin », hors ateliers : sans MLFLOW_TRACKING_URI,
    # cet appel ne fait rien et la sortie reste exactement celle d'avant.
    run = suivi.enregistrer(params, metriques, pipeline)
    if run:
        metriques["run_mlflow"] = run

    return metriques


if __name__ == "__main__":
    log = journal.configurer("train")
    journal.demarrer(log, "entraînement")
    m = entrainer()
    journal.dire(log, "Modèle entraîné et sauvegardé dans models/modele.pkl")
    for cle, valeur in m.items():
        journal.dire(log, f"  {cle:<16} {valeur}")
