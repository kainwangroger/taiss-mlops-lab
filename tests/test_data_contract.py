"""
Étage 2 — tests de contrat de données.

C'est le test qui vous sauvera le plus souvent. En production, la majorité des
incidents viennent de la donnée, pas du modèle : une colonne renommée, un type
qui change, une catégorie nouvelle, une borne dépassée.

------------------------------------------------------------------------------
ATELIER 1, étape 2
Trois tests sont déjà écrits pour vous servir de modèle. Trois autres sont à
compléter : cherchez les marqueurs « À COMPLÉTER ».
Le contrat de référence se trouve dans src/features.py, dictionnaire CONTRAT.
Le code à coller est dans docs/ATELIER-1.md, étape 5.
------------------------------------------------------------------------------
"""

import pathlib

import pandas as pd
import pytest
import yaml

from src.features import CIBLE, COLONNES_ATTENDUES, CONTRAT

RACINE = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def donnees():
    with open(RACINE / "params.yaml", encoding="utf-8") as f:
        params = yaml.safe_load(f)
    return pd.read_csv(RACINE / params["donnees"]["reference"])


# --- Déjà écrits : servez-vous en comme modèle -------------------------------

def test_toutes_les_colonnes_attendues_sont_presentes(donnees):
    manquantes = set(COLONNES_ATTENDUES + [CIBLE]) - set(donnees.columns)
    assert not manquantes, f"colonnes manquantes : {sorted(manquantes)}"


def test_aucune_valeur_manquante(donnees):
    nuls = donnees[COLONNES_ATTENDUES].isna().sum()
    en_faute = nuls[nuls > 0]
    assert en_faute.empty, f"valeurs manquantes : {en_faute.to_dict()}"


def test_les_bornes_du_contrat_sont_respectees(donnees):
    for colonne, regle in CONTRAT.items():
        if regle["type"] != "numerique":
            continue
        serie = donnees[colonne]
        assert serie.min() >= regle["min"], (
            f"{colonne} descend à {serie.min()}, minimum du contrat {regle['min']}"
        )
        assert serie.max() <= regle["max"], (
            f"{colonne} monte à {serie.max()}, maximum du contrat {regle['max']}"
        )


# --- À COMPLÉTER pendant l'atelier 1 -----------------------------------------

def test_les_categories_sont_celles_du_contrat(donnees):
    """
    À COMPLÉTER.

    Vérifiez qu'aucune catégorie inconnue n'apparaît dans les colonnes
    catégorielles du CONTRAT. C'est ce test qui aurait détecté l'arrivée de
    la catégorie « marchand » avant qu'elle n'atteigne la production.

    Indice : parcourez CONTRAT, gardez les règles de type « categoriel »,
    et comparez set(donnees[colonne].unique()) à set(regle["categories"]).
    """
    pytest.skip("À compléter pendant l'atelier 1")


def test_les_types_sont_numeriques(donnees):
    """
    À COMPLÉTER.

    Vérifiez que chaque colonne numérique du CONTRAT est bien d'un type
    numérique. Une colonne montant arrivant en texte est un incident classique
    quand la source change de format d'export.

    Indice : pandas.api.types.is_numeric_dtype.
    """
    pytest.skip("À compléter pendant l'atelier 1")


def test_la_cible_est_binaire_et_rare(donnees):
    """
    À COMPLÉTER.

    Vérifiez deux choses : que la cible ne prend que les valeurs 0 et 1, et
    que le taux de fraude reste plausible — disons entre 0,1 % et 5 %.

    Un taux de fraude qui bondit à 40 % ne signale pas une vague de fraude :
    il signale une erreur de jointure en amont.
    """
    pytest.skip("À compléter pendant l'atelier 1")


