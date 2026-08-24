"""
Étage 1 — tests unitaires du code.

Rapides, déterministes, exécutés à chaque commit. Ils ne testent pas le modèle :
ils testent les transformations, qui sont des fonctions pures.
"""

import pandas as pd
import pytest

from src.features import (
    COLONNES_ATTENDUES,
    compte_jeune,
    construire_features,
    est_nocturne,
    montant_par_transaction,
)


def test_est_nocturne_borne_inferieure():
    assert est_nocturne(pd.Series([0])).iloc[0] == 1


def test_est_nocturne_borne_superieure():
    assert est_nocturne(pd.Series([4])).iloc[0] == 1
    assert est_nocturne(pd.Series([5])).iloc[0] == 0


def test_est_nocturne_journee():
    heures = pd.Series([9, 13, 18, 23])
    assert est_nocturne(heures).sum() == 0


def test_compte_jeune():
    assert compte_jeune(pd.Series([10])).iloc[0] == 1
    assert compte_jeune(pd.Series([59])).iloc[0] == 1
    assert compte_jeune(pd.Series([60])).iloc[0] == 0


def test_montant_par_transaction_evite_division_par_zero():
    resultat = montant_par_transaction(pd.Series([1000.0]), pd.Series([0]))
    assert resultat.iloc[0] == pytest.approx(1000.0)


def test_montant_par_transaction_valeur():
    resultat = montant_par_transaction(pd.Series([1000.0]), pd.Series([3]))
    assert resultat.iloc[0] == pytest.approx(250.0)


def test_construire_features_ne_modifie_pas_l_entree():
    df = pd.DataFrame(
        {
            "montant": [5000.0],
            "heure": [2],
            "frequence_7j": [4],
            "anciennete_jours": [30],
            "type_contrepartie": ["agent"],
        }
    )
    colonnes_avant = list(df.columns)
    construire_features(df)
    assert list(df.columns) == colonnes_avant


def test_construire_features_ajoute_les_variables_derivees():
    df = pd.DataFrame(
        {
            "montant": [5000.0],
            "heure": [2],
            "frequence_7j": [4],
            "anciennete_jours": [30],
            "type_contrepartie": ["agent"],
        }
    )
    sortie = construire_features(df)
    for attendue in ("est_nocturne", "compte_jeune", "montant_par_transaction"):
        assert attendue in sortie.columns
    assert all(c in sortie.columns for c in COLONNES_ATTENDUES)
