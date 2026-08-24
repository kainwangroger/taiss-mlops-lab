"""
Étage 4 — tests d'intégration du service.

L'API répond, la forme de la réponse est correcte, la version du modèle est
présente, et le point de terminaison des métriques est exposé.
"""

import pathlib

import pytest
from fastapi.testclient import TestClient

RACINE = pathlib.Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    not (RACINE / "models" / "modele.pkl").exists(),
    reason="modèle absent — lancez python -m src.train",
)


@pytest.fixture(scope="module")
def client():
    from src.serve import app

    return TestClient(app)


TRANSACTION = {
    "montant": 45000,
    "heure": 21,
    "frequence_7j": 4,
    "anciennete_jours": 35,
    "type_contrepartie": "particulier",
}


def test_health_repond(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["statut"] == "ok"


def test_predict_repond_200(client):
    r = client.post("/predict", json=TRANSACTION)
    assert r.status_code == 200


def test_la_reponse_contient_la_version_du_modele(client):
    """Sans ce champ, aucun incident n'est traçable a posteriori."""
    r = client.post("/predict", json=TRANSACTION)
    assert "version_modele" in r.json()
    assert r.json()["version_modele"]


def test_le_score_est_une_probabilite(client):
    score = client.post("/predict", json=TRANSACTION).json()["score"]
    assert 0.0 <= score <= 1.0


def test_une_heure_invalide_est_refusee(client):
    charge = {**TRANSACTION, "heure": 42}
    assert client.post("/predict", json=charge).status_code == 422


def test_un_montant_negatif_est_refuse(client):
    charge = {**TRANSACTION, "montant": -1}
    assert client.post("/predict", json=charge).status_code == 422


def test_une_categorie_inconnue_ne_fait_pas_planter_le_service(client):
    """
    Le service répond 200 sur une catégorie qu'il n'a jamais vue.

    C'est le comportement voulu — mais c'est aussi le piège : il répond
    normalement tout en se trompant. Seul le monitoring le révélera.
    """
    charge = {**TRANSACTION, "type_contrepartie": "marchand"}
    r = client.post("/predict", json=charge)
    assert r.status_code == 200


def test_le_point_de_terminaison_metriques_est_expose(client):
    """Le service doit être interrogeable par Prometheus."""
    r = client.get("/metrics")
    assert r.status_code == 200


def test_les_metriques_metier_sont_exposees(client):
    """
    Passe une fois l'atelier 2 terminé.

    Tant que les métriques ne sont pas déclarées, ce test est ignoré plutôt
    qu'en échec : la chaîne d'intégration reste verte, et ce test devient
    votre indicateur de progression pendant l'atelier 2.
    """
    texte = client.get("/metrics").text
    if "predictions_total" not in texte:
        pytest.skip("métriques métier absentes — à ajouter pendant l'atelier 2")
    assert "version_modele" in texte, (
        "les métriques doivent être étiquetées par version de modèle"
    )
    assert "inference_secondes" in texte, "la latence n'est pas instrumentée"
