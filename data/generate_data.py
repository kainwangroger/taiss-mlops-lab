"""
Génère les deux jeux de données du lab.

  reference_2025.csv : le trafic sur lequel le modèle a été entraîné.
  drifted_2026.csv   : le trafic de 2026, après le lancement du paiement marchand.

Les deux fichiers sont versionnés dans le dépôt : ce script n'a pas besoin d'être
relancé pendant le lab. Il est là pour que la dérive soit reproductible et
inspectable, pas pour être exécuté par les participants.

La dérive injectée est volontairement de trois natures différentes :

  1. Dérive des données  — le montant et l'heure changent de distribution.
  2. Nouvelle catégorie  — le type de contrepartie « marchand » n'existait pas
                           dans le jeu d'entraînement.
  3. Dérive du concept   — chez les marchands, la relation entre les variables
                           et la fraude s'inverse : en 2025 la fraude passait par
                           de gros montants nocturnes ; chez les marchands elle
                           passe par de petits montants répétés en fin de journée.

C'est le point 3 qui rend le réentraînement naïf inefficace, et c'est le piège
pédagogique de l'atelier 3.
"""

import numpy as np
import pandas as pd

GRAINE = 42
CHEMIN = __file__.rsplit("/", 1)[0]

MU_2025, SIGMA_2025 = 8.10, 0.85          # log-montant du trafic P2P
MU_MARCHAND, SIGMA_MARCHAND = 9.55, 0.62  # log-montant du paiement marchand


def _heures(rng, n, diurne=False):
    """Heures de la journée. En 2025 le trafic P2P est majoritairement nocturne."""
    if diurne:
        h = rng.normal(13.5, 2.6, n)
    else:
        h = np.where(
            rng.random(n) < 0.65,
            rng.normal(20.5, 2.4, n),
            rng.normal(9.0, 2.2, n),
        )
    return np.clip(np.round(h), 0, 23).astype(int)


# Netteté du lien entre le score et l'étiquette. Plus la valeur est élevée,
# moins l'étiquette est bruitée — et plus le modèle peut apprendre. Sur des
# données pédagogiques, on veut un signal net : l'objectif du lab est de
# montrer la dérive, pas de lutter contre un bruit irréductible.
NETTETE = 8.0


def _calibrer_intercept(score, prevalence_cible):
    """Trouve par bissection l'intercept qui donne la prévalence visée."""
    bas, haut = -60.0, 60.0
    for _ in range(80):
        milieu = (bas + haut) / 2
        p = 1 / (1 + np.exp(-NETTETE * (score - milieu)))
        if p.mean() > prevalence_cible:
            bas = milieu
        else:
            haut = milieu
    return (bas + haut) / 2


def _tirer_fraude(rng, score, prevalence_cible):
    intercept = _calibrer_intercept(score, prevalence_cible)
    proba = 1 / (1 + np.exp(-NETTETE * (score - intercept)))
    return (rng.random(len(score)) < proba).astype(int)


def generer_2025(n=20000, prevalence=0.009):
    rng = np.random.default_rng(GRAINE)

    log_montant = rng.normal(MU_2025, SIGMA_2025, n)
    montant = np.round(np.exp(log_montant), 0)
    heure = _heures(rng, n)
    frequence_7j = rng.poisson(3.2, n)
    anciennete_jours = rng.integers(5, 2200, n)
    type_contrepartie = rng.choice(
        ["particulier", "agent", "facture"], size=n, p=[0.72, 0.21, 0.07]
    )

    z_montant = (log_montant - MU_2025) / SIGMA_2025

    # Signal 2025 : gros montant, compte jeune, rafale, nuit, contrepartie agent.
    score = (
        1.05 * z_montant
        + 1.30 * (anciennete_jours < 90)
        + 1.20 * (frequence_7j >= 7)
        + 1.00 * ((heure >= 0) & (heure <= 4))
        + 0.60 * (type_contrepartie == "agent")
    )
    fraude = _tirer_fraude(rng, score, prevalence)

    return pd.DataFrame(
        {
            "montant": montant,
            "heure": heure,
            "frequence_7j": frequence_7j,
            "anciennete_jours": anciennete_jours,
            "type_contrepartie": type_contrepartie,
            "fraude": fraude,
        }
    )


def generer_2026(n=8000, prevalence=0.013):
    """Le trafic de 2026, après le lancement du paiement marchand en mars."""
    rng = np.random.default_rng(GRAINE + 1)

    est_marchand = rng.random(n) < 0.42

    # 1. Dérive des données : les paiements marchands sont plus gros et diurnes.
    log_montant = np.where(
        est_marchand,
        rng.normal(MU_MARCHAND, SIGMA_MARCHAND, n),
        rng.normal(MU_2025, SIGMA_2025, n),
    )
    montant = np.round(np.exp(log_montant), 0)
    heure = np.where(est_marchand, _heures(rng, n, diurne=True), _heures(rng, n))
    frequence_7j = np.where(est_marchand, rng.poisson(7.1, n), rng.poisson(3.3, n))
    anciennete_jours = rng.integers(5, 2400, n)

    # 2. Nouvelle catégorie, absente du jeu d'entraînement.
    type_contrepartie = np.where(
        est_marchand,
        "marchand",
        rng.choice(["particulier", "agent", "facture"], size=n, p=[0.72, 0.21, 0.07]),
    )

    z_p2p = (log_montant - MU_2025) / SIGMA_2025
    z_marchand = (log_montant - MU_MARCHAND) / SIGMA_MARCHAND

    score_p2p = (
        1.05 * z_p2p
        + 1.30 * (anciennete_jours < 90)
        + 1.20 * (frequence_7j >= 7)
        + 1.00 * ((heure >= 0) & (heure <= 4))
        + 0.60 * (type_contrepartie == "agent")
    )
    # 3. Dérive du concept : chez les marchands, le signe du montant s'inverse.
    score_marchand = (
        -1.15 * z_marchand
        + 1.40 * (frequence_7j >= 12)
        + 1.10 * (anciennete_jours < 60)
        + 0.90 * (heure >= 17)
    )
    score = np.where(est_marchand, score_marchand, score_p2p)
    fraude = _tirer_fraude(rng, score, prevalence)

    return pd.DataFrame(
        {
            "montant": montant,
            "heure": heure,
            "frequence_7j": frequence_7j,
            "anciennete_jours": anciennete_jours,
            "type_contrepartie": type_contrepartie,
            "fraude": fraude,
        }
    )


if __name__ == "__main__":
    ref = generer_2025()
    der = generer_2026()
    ref.to_csv(f"{CHEMIN}/reference_2025.csv", index=False)
    der.to_csv(f"{CHEMIN}/drifted_2026.csv", index=False)
    print(f"reference_2025.csv : {len(ref):>6} lignes · {ref.fraude.mean():.2%} de fraude")
    print(f"drifted_2026.csv   : {len(der):>6} lignes · {der.fraude.mean():.2%} de fraude")
    print(f"  part marchands   : {(der.type_contrepartie == 'marchand').mean():.1%}")
    print(f"  montant médian   : 2025 {ref.montant.median():>9,.0f}"
          f"  |  2026 {der.montant.median():>9,.0f}")
