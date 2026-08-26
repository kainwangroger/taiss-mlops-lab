"""
Suivi d'expériences MLflow — section « aller plus loin », hors ateliers.

Ce module est **entièrement optionnel**. Sans lui, le lab fonctionne à
l'identique : `src/train.py` l'appelle, il ne fait rien, et l'entraînement se
déroule comme avant.

Il ne s'active que si les trois conditions sont réunies :

1. la variable d'environnement `MLFLOW_TRACKING_URI` est définie ;
2. le paquet `mlflow` est installé (`requirements-plus-loin.txt`) ;
3. le serveur répond.

Si l'une manque, on renonce en silence. C'est délibéré : `src/train.py` tourne
aussi pendant la construction de l'image Docker et dans la chaîne d'intégration,
deux contextes où aucun serveur MLflow n'existe. Un suivi d'expériences qui fait
échouer un build est pire que pas de suivi du tout.

Ce que le lab ne fait pas encore, et que MLflow apporterait :

    reports/metriques.json est écrasé à chaque entraînement. Comparer deux runs
    est impossible. C'est le trou que ce module commence à combler.

Usage :
    MLFLOW_TRACKING_URI=http://localhost:5001 python -m src.train
"""

import os

EXPERIENCE = "fraude-mobile-money"


def enregistrer(params: dict, metriques: dict, pipeline=None) -> str | None:
    """
    Enregistre un entraînement dans MLflow. Renvoie l'identifiant du run, ou
    None si le suivi n'est pas actif.
    """
    uri = os.environ.get("MLFLOW_TRACKING_URI")
    if not uri:
        return None

    try:
        import mlflow
        import mlflow.sklearn
    except ImportError:
        return None

    try:
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(EXPERIENCE)

        with mlflow.start_run() as run:
            mlflow.log_params(
                {
                    "version_modele": params["version_modele"],
                    "graine": params["graine"],
                    "part_test": params["donnees"]["part_test"],
                    "seuil_decision": params["evaluation"]["seuil_decision"],
                    **{f"modele_{k}": v for k, v in params["modele"].items()},
                }
            )
            mlflow.log_metrics(
                {
                    cle: valeur
                    for cle, valeur in metriques.items()
                    if isinstance(valeur, int | float)
                }
            )
            # Le seuil d'acceptation est ce qui décide d'une promotion : il a sa
            # place à côté de la métrique qu'il juge.
            mlflow.set_tag("seuil_f1_exige", params["evaluation"]["seuil_f1"])
            tenu = metriques["f1"] >= params["evaluation"]["seuil_f1"]
            mlflow.set_tag("verdict", "OK" if tenu else "REFUSÉ")

            if pipeline is not None:
                # Isolé : l'API de log_model a changé entre MLflow 2 et 3. Si
                # elle bouge encore, on perd l'artefact, pas le run entier.
                try:
                    mlflow.sklearn.log_model(pipeline, artifact_path="modele")
                except Exception:  # noqa: BLE001
                    mlflow.set_tag("modele_non_enregistre", "true")

            return run.info.run_id
    except Exception:  # noqa: BLE001
        # Serveur injoignable, version incompatible, disque plein : on renonce.
        # L'entraînement, lui, a réussi — c'est ce qui compte.
        return None
