# Atelier 3 — Voir la dérive

**10 minutes de manipulation, 5 de restitution · en binôme**

À la fin de cet atelier, vous aurez produit un rapport de dérive, identifié les
variables touchées, et formulé une décision argumentée.

---

## Le contexte

Le dépôt contient deux jeux de données :

| Fichier | Ce que c'est |
|---|---|
| `data/reference_2025.csv` | le trafic sur lequel le modèle a été entraîné |
| `data/drifted_2026.csv` | le trafic de 2026, après le lancement du paiement marchand en mars |

Depuis ce lancement, l'opérateur traite des paiements vers des commerçants :
montants plus élevés, horaires diurnes, comptes plus actifs. Une nouvelle valeur
`marchand` apparaît dans le type de contrepartie. **Aucune ligne de code du
modèle n'a changé.**

---

## Étape 1 — Rejouer le trafic dérivé (3 min)

Assurez-vous que la pile de l'atelier 2 tourne encore, puis :

```bash
python -m src.replay --input data/drifted_2026.csv --n 800
```

Comparez le **taux de signalement** affiché à celui de l'atelier 2. Regardez
aussi le score moyen glissant dans Grafana.

---

## Étape 2 — Produire le rapport (3 min)

```bash
python -m src.drift_report
```

Le rapport s'écrit dans `reports/derive.html`. Ouvrez-le dans votre navigateur.

Le PSI se lit ainsi :

| Valeur | Lecture |
|---|---|
| moins de 0,10 | stable |
| 0,10 à 0,25 | à surveiller |
| plus de 0,25 | dérive avérée |

---

## Étape 3 — Lire (2 min)

Répondez à ces trois questions dans votre binôme :

1. **Quelles variables ont dérivé, et laquelle le plus ?**
2. **Une variable est restée stable. Laquelle, et pourquoi est-ce rassurant ?**
3. **Qu'est-ce que le rapport signale sur `type_contrepartie` que le PSI seul
   ne dirait pas ?**

---

## Étape 4 — Décider (2 min)

Une phrase, à dire à la restitution : **ce que vous feriez lundi matin, et
pourquoi.**

Trois options sont sur la table :

- réentraîner le modèle sur les données récentes,
- ajuster le seuil de décision,
- ne rien faire pour l'instant et instrumenter davantage.

> **Attention.** « Réentraîner » est la réponse réflexe. Avant de la donner,
> demandez-vous sur *quelles* données vous réentraîneriez, et si les étiquettes
> de 2026 sont déjà disponibles — sachant que les analystes mettent trois jours
> à confirmer un cas signalé.

---

## Critères de réussite

- [ ] Le rapport est produit et lisible
- [ ] Le binôme nomme au moins deux variables dérivées avec un ordre de grandeur
- [ ] La nouvelle catégorie a été repérée
- [ ] La décision est argumentée, quelle qu'elle soit

---

## Si vous avez fini en avance

Segmentez. La dérive touche-t-elle tout le trafic, ou seulement le segment
marchand ? Comparez le taux de signalement sur les deux populations :

```python
import pandas as pd
d = pd.read_csv("reports/predictions.csv")
print(d.groupby(d.type_contrepartie == "marchand").signalee.mean())
```

Ce que vous trouverez change complètement la décision à prendre.
