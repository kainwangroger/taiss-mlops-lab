"""
Service de prédiction.

------------------------------------------------------------------------------
NOTE POUR LES ENCADRANTS
Ce fichier est l'emplacement prévu pour le service produit lors de la séance
« Exposer un modèle en API » du mercredi. Si vous disposez du fichier des
participants, remplacez le corps de ce module en conservant :
  - la route POST /predict
  - le champ "version_modele" dans la réponse
  - la route GET /metrics
Le reste du lab ne dépend de rien d'autre.
------------------------------------------------------------------------------

En l'état, ce service fonctionne mais n'est pas observable : il répond, et
personne ne sait ce qu'il répond. C'est l'objet de l'atelier 2.

Usage :
    uvicorn src.serve:app --host 0.0.0.0 --port 8000
"""

import pathlib
import time

import joblib
import pandas as pd
import yaml
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from src.features import construire_features

RACINE = pathlib.Path(__file__).resolve().parents[1]

with open(RACINE / "params.yaml", encoding="utf-8") as f:
    PARAMS = yaml.safe_load(f)

VERSION_MODELE = PARAMS["version_modele"]
SEUIL_DECISION = PARAMS["evaluation"]["seuil_decision"]

app = FastAPI(title="Détection de fraude mobile money", version=VERSION_MODELE)
_modele = None

CATEGORIES_CONNUES = {"particulier", "agent", "facture"}
_derniers_scores: list = []


# =============================================================================
# ATELIER 2 — étape 1 : déclarer les métriques
#
# Trois primitives suffisent :
#   Counter   ce qui ne fait que monter        -> nombre de prédictions
#   Histogram une distribution de valeurs      -> latence d'inférence
#   Gauge     une valeur qui monte et descend  -> score moyen glissant
#
# Complétez l'import ci-dessus :
#     from prometheus_client import Counter, Gauge, Histogram
#
# Puis déclarez ici vos métriques. Étiquetez TOUJOURS par version de modèle :
# sans ce label, impossible de comparer un champion et un challenger, ni
# d'imputer une dégradation à un déploiement précis.
#
#     PREDICTIONS = Counter(
#         "predictions_total",
#         "Nombre de prédictions servies",
#         ["version_modele", "classe"],
#     )
#     LATENCE = Histogram(...)
#     SCORE_MOYEN = Gauge(...)
#     CATEGORIE_INCONNUE = Counter(...)
#
# Le corrigé est sur la branche solution-atelier-2.
# =============================================================================


class Transaction(BaseModel):
    montant: float = Field(..., ge=0, examples=[45000])
    heure: int = Field(..., ge=0, le=23, examples=[21])
    frequence_7j: int = Field(..., ge=0, examples=[4])
    anciennete_jours: int = Field(..., ge=0, examples=[35])
    type_contrepartie: str = Field(..., examples=["particulier"])


def charger_modele():
    global _modele
    if _modele is None:
        chemin = RACINE / "models" / "modele.pkl"
        if not chemin.exists():
            raise RuntimeError(
                "models/modele.pkl est absent. Lancez d'abord : python -m src.train"
            )
        _modele = joblib.load(chemin)
    return _modele


@app.get("/health")
def sante():
    return {"statut": "ok", "version_modele": VERSION_MODELE}


@app.post("/predict")
def predire(transaction: Transaction):
    modele = charger_modele()
    debut = time.perf_counter()

    df = pd.DataFrame([transaction.model_dump()])

    # ATELIER 2 — étape 2a
    # Une catégorie inconnue ne fait pas planter le service : elle le fait se
    # tromper en silence. Comptez-la ici, faute de pouvoir la refuser.
    #
    #     if transaction.type_contrepartie not in CATEGORIES_CONNUES:
    #         CATEGORIE_INCONNUE.labels(VERSION_MODELE, "type_contrepartie").inc()

    score = float(modele.predict_proba(construire_features(df))[0][1])
    signalee = int(score >= SEUIL_DECISION)
    duree = time.perf_counter() - debut

    # ATELIER 2 — étape 2b
    # Observez la latence, comptez la prédiction, mettez à jour le score moyen.
    #
    #     LATENCE.labels(VERSION_MODELE).observe(duree)
    #     PREDICTIONS.labels(VERSION_MODELE, "signalee" if signalee else "normale").inc()
    #
    #     _derniers_scores.append(score)
    #     del _derniers_scores[:-200]
    #     SCORE_MOYEN.labels(VERSION_MODELE).set(
    #         sum(_derniers_scores) / len(_derniers_scores)
    #     )

    return {
        "score": round(score, 4),
        "signalee": bool(signalee),
        "seuil_decision": SEUIL_DECISION,
        "version_modele": VERSION_MODELE,
        "latence_ms": round(duree * 1000, 2),
    }


@app.get("/metrics")
def metriques():
    """
    Point de terminaison interrogé par Prometheus toutes les cinq secondes.

    Il répond déjà — mais tant que l'étape 1 n'est pas faite, il n'expose que
    les métriques par défaut du processus Python. Aucune information sur le
    modèle. C'est précisément la situation de départ de l'atelier 2 : le
    service est joignable, mais il n'est pas observable.
    """
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
