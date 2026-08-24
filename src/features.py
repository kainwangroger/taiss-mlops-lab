"""
Transformations appliquées aux données avant le modèle.

Règle du lab : toute transformation vit ici, sous forme de fonction pure.
Une fonction pure prend une entrée, renvoie une sortie, ne modifie rien
d'autre — c'est ce qui la rend testable en deux lignes.
"""

import pandas as pd

COLONNES_NUMERIQUES = ["montant", "heure", "frequence_7j", "anciennete_jours"]
COLONNES_CATEGORIELLES = ["type_contrepartie"]
COLONNES_ATTENDUES = COLONNES_NUMERIQUES + COLONNES_CATEGORIELLES
CIBLE = "fraude"

# Le contrat de données : ce que le modèle a le droit de recevoir.
# C'est la référence utilisée par tests/test_data_contract.py.
CONTRAT = {
    "montant": {"min": 0, "max": 5_000_000, "type": "numerique"},
    "heure": {"min": 0, "max": 23, "type": "numerique"},
    "frequence_7j": {"min": 0, "max": 200, "type": "numerique"},
    "anciennete_jours": {"min": 0, "max": 20_000, "type": "numerique"},
    "type_contrepartie": {
        "categories": ["particulier", "agent", "facture"],
        "type": "categoriel",
    },
}


def est_nocturne(heure: pd.Series) -> pd.Series:
    """Vrai entre minuit et 4 h inclus."""
    return ((heure >= 0) & (heure <= 4)).astype(int)


def compte_jeune(anciennete_jours: pd.Series, seuil: int = 60) -> pd.Series:
    """Vrai si le compte a moins de `seuil` jours."""
    return (anciennete_jours < seuil).astype(int)


def montant_par_transaction(montant: pd.Series, frequence_7j: pd.Series) -> pd.Series:
    """Montant rapporté à l'intensité d'usage du compte sur sept jours."""
    return montant / (frequence_7j + 1)


def construire_features(df: pd.DataFrame) -> pd.DataFrame:
    """Assemble les variables dérivées. Ne modifie pas le DataFrame reçu."""
    sortie = df[COLONNES_ATTENDUES].copy()
    sortie["est_nocturne"] = est_nocturne(sortie["heure"])
    sortie["compte_jeune"] = compte_jeune(sortie["anciennete_jours"])
    sortie["montant_par_transaction"] = montant_par_transaction(
        sortie["montant"], sortie["frequence_7j"]
    )
    return sortie


def colonnes_numeriques_finales() -> list:
    return COLONNES_NUMERIQUES + [
        "est_nocturne",
        "compte_jeune",
        "montant_par_transaction",
    ]
