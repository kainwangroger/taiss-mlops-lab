# Atelier 3 — Voir la dérive

**15 minutes · ensemble, étape par étape**

Le modèle n'a pas changé depuis l'atelier 2. Vous allez lui envoyer le trafic de
2026 et regarder ce qui se passe.

**Le contexte :** en mars 2026, l'opérateur a lancé le paiement marchand. Des
commerçants encaissent désormais des paiements — montants plus élevés, horaires
diurnes, comptes plus actifs — et une valeur `marchand` apparaît dans le type de
contrepartie. **Aucune ligne du modèle n'a été touchée.**

---

## Avant de commencer

La pile de l'atelier 2 doit tourner encore.

```bash
docker ps
```

**Vous devez voir** trois conteneurs : `taiss-api`, `taiss-prometheus` et
`taiss-grafana`. Si la liste est vide :

```bash
docker compose up -d --build
```

---

## Étape 1 — Rejouer le trafic 2026

```bash
python -m src.replay --input data/drifted_2026.csv --n 800 --url http://localhost:8001
```

**Vous devez voir**, à la fin :

```text
800 prédictions en 41.2 s (19 req/s)
score moyen        : 0.1487
taux de signalement: 15.00%
```

**Comparez avec l'atelier 2 : c'était 0,60 %.**

Le taux de signalement a été **multiplié par vingt-cinq**. Le modèle est le
même, le code est le même, le seuil est le même. Seules les données ont changé.

Ouvrez Grafana (<http://localhost:3002>) et regardez le score moyen glissant
remonter.

---

## Étape 2 — Produire le rapport de dérive

```bash
python -m src.drift_report
```

**Vous devez voir :**

```text
variable                   PSI   verdict
--------------------------------------------------------
type_contrepartie        5.666   DÉRIVE AVÉRÉE  ← nouvelle catégorie : marchand
montant                  0.470   DÉRIVE AVÉRÉE
heure                    0.450   DÉRIVE AVÉRÉE
frequence_7j             0.443   DÉRIVE AVÉRÉE
anciennete_jours         0.055   STABLE

Rapport écrit dans reports/derive.html — ouvrez-le dans votre navigateur.
```

---

## Étape 3 — Lire le rapport

Ouvrez `reports/derive.html` dans votre navigateur — double-cliquez sur le
fichier, ou glissez-le dans un onglet.

**Comment se lit le PSI :**

| Valeur | Ce que ça veut dire |
|---|---|
| moins de 0,10 | la variable est stable |
| 0,10 à 0,25 | à surveiller |
| plus de 0,25 | la dérive est avérée |

**Trois choses à remarquer, dans l'ordre.**

**1. Quatre variables sur cinq ont dérivé.** `type_contrepartie` domine très
largement : PSI 5,666, soit vingt fois le seuil d'alerte. Les trois autres
(`montant`, `heure`, `frequence_7j`) dérivent ensemble et pour la même raison —
les paiements marchands sont plus gros, plus diurnes, faits par des comptes plus
actifs. Ce n'est pas trois dérives, c'est une seule vue sous trois angles.

**2. Une variable est restée stable :** `anciennete_jours`, PSI 0,055.

C'est rassurant, et pas pour la raison qu'on croit. **Si tout avait dérivé, le
premier suspect serait le pipeline, pas le monde.** Une extraction cassée ou une
jointure qui déraille font bouger toutes les colonnes à la fois. Qu'une variable
soit restée exactement là où elle était prouve que la collecte fonctionne — donc
que la dérive des quatre autres est réelle.

**3. Une catégorie nouvelle est apparue :** `marchand`.

C'est ce que le PSI seul ne dirait pas. Un PSI élevé peut simplement signaler un
changement de proportions entre catégories connues. Ici, c'est une valeur que le
modèle **n'a jamais vue à l'entraînement**.

Regardez `src/train.py` :

```python
OneHotEncoder(handle_unknown="ignore")
```

Une catégorie inconnue n'est pas refusée : elle est encodée en **vecteur nul**.
Le service ne plante pas, ne journalise aucune erreur, répond en 200 — et traite
ces lignes comme n'appartenant à aucune catégorie. C'est exactement ce que le
test que vous avez écrit à l'atelier 1 aurait attrapé, en amont.

---

## Étape 4 — Regarder par segment

```bash
python -c "import pandas as pd; d=pd.read_csv('reports/predictions.csv'); print(d.groupby('type_contrepartie').signalee.mean().mul(100).round(1))"
```

**Vous devez voir :**

```text
type_contrepartie
agent           3.2
facture         2.9
marchand       33.1
particulier     0.6
```

**Le segment `particulier` est resté exactement à son niveau de 2025 : 0,6 %.**
Le segment `marchand`, lui, en signale un tiers — sur 344 transactions.

Le modèle n'est donc pas cassé. La dérive est **entièrement localisée** sur une
population qui n'existait pas quand il a été entraîné. C'est le chiffre le plus
important de tout le lab.

---

## Étape 5 — Décider

Discussion en binôme, **cinq minutes**. Une phrase, qui commence par :

> Lundi matin, je … parce que …

Trois options sont sur la table :

| Option | Ce qu'il faut se demander avant |
|---|---|
| **Réentraîner** sur les données récentes | Sur *quelles* données ? Les analystes mettent trois jours à confirmer un cas signalé — vos étiquettes 2026 s'arrêtent donc il y a trois jours, et elles sont rares sur le segment marchand |
| **Ajuster le seuil** de décision | Combien coûte un faux positif (charge des analystes) face à un faux négatif (fraude non détectée) ? Ce n'est pas une décision technique |
| **Ne rien faire** et instrumenter davantage | Combien de temps pouvez-vous laisser un tiers du trafic marchand partir en revue manuelle ? |

**« Réentraîner » est la réponse réflexe, et c'est la plus faible** si elle ne
précise pas sur quoi.

Une réponse défendable, pour donner le ton :

> *Lundi matin, je route le segment marchand vers une revue manuelle et je laisse
> le modèle sur le reste, parce que la dérive y est localisée et que je n'aurai
> pas d'étiquettes fiables avant plusieurs semaines.*

---

## Ce qui se déclenche tout seul dans Grafana

Pendant que vous faisiez l'étape 1, **deux alertes sont passées au rouge sans
que personne ne les provoque.** Ouvrez Grafana → **Alerting → Alert rules**.

| Alerte | Délai | Cause |
|---|---|---|
| Catégorie inconnue reçue par le modèle | moins d'une minute | l'arrivée de `marchand` |
| Taux de signalement anormalement élevé | environ 3 minutes | 15 % contre 0,6 % en 2025 |

**Ce n'est pas un incident, c'est le comportement attendu.** Les règles sont
dans `monitoring/grafana/provisioning/alerting/regles.yaml`, chargées au
démarrage de Grafana.

Deux choses valent d'être remarquées.

**Le délai de trois minutes n'est pas une lenteur, c'est un réglage.** L'alerte
passe d'abord en `pending`, puis en `firing`. Ce délai est le paramètre `for` :
une alerte attend d'être sûre avant de déranger quelqu'un. Une alerte sans
`for` finit toujours par être ignorée.

**L'alerte « catégorie inconnue » signale une panne dont le service ne se plaint
pas.** L'API répond 200, la latence est normale, aucune erreur n'est
journalisée — et les prédictions sur ces lignes ne veulent rien dire.

Aucun destinataire n'est configuré : les alertes changent d'état dans Grafana
mais ne partent nulle part. C'est volontaire. Router une alerte demande de
décider **qui** est réveillé et **pour quoi**, ce qui n'est pas une décision
technique.

---

## L'atelier 3 est terminé

Vous avez :

- [x] vu un modèle décrocher sans qu'une ligne de code ait changé ;
- [x] identifié les variables touchées et celle qui ne l'est pas ;
- [x] repéré la catégorie que le modèle n'a jamais vue ;
- [x] formulé une décision qui tient compte des étiquettes.

`reports/derive.html` est produit, et le tableau par segment est calculé.

---

## Si ça bloque

| Ce que vous voyez | Ce qu'il faut faire |
|---|---|
| `Connection refused` | La pile est arrêtée : `docker compose up -d` |
| Le taux reste à 0,60 % | Vous avez rejoué le mauvais fichier : vérifiez `--input data/drifted_2026.csv` |
| Tous les PSI sont à 0 | Vous comparez la référence à elle-même : vérifiez `derive:` dans `params.yaml` |
| La section « segment » est vide | `reports/predictions.csv` date de l'atelier 2 : refaites l'étape 1 |
| `reports/derive.html` n'existe pas | Relancez `python -m src.drift_report` |

---

## Les trois ateliers sont finis — voir le pipeline en entier

Vous avez tout fait à la main, commande par commande, pour comprendre à quoi
sert chaque étape. Le dépôt contient une application qui enchaîne les mêmes
étapes automatiquement, et les montre.

C'est le moment de la lancer : maintenant, vous savez ce qu'elle fait.

```bash
pip install -r requirements-console.txt
python -m streamlit run src/console.py --server.port 8501
```

Ouvrez <http://localhost:8501>, onglet **Pipeline**, puis **▶ Lancer le
pipeline**.

Elle existe aussi en conteneur, mais il faut la demander explicitement — la pile
des ateliers ne la démarre pas :

```bash
docker compose --profile plateforme up -d --build   # puis http://localhost:8502
```

**Vous devez voir** le graphe s'allumer case par case, et les sept étapes finir
au vert :

```text
① Chargement       ✓  20 000 lignes × 6 colonnes
② Contrat          ✓  tous les contrôles passent          ← votre atelier 1
③ Prétraitement    ✓  3 variables dérivées
④ Entraînement     ✓  F1 = 0.7273 · AUC = 0.9963
⑤ Porte de qualité ✓  F1 0.7273 ≥ seuil 0.6              ← votre atelier 1
⑥ Prédiction       ✓  800 scorées · 15.00% signalées      ← votre atelier 3
⑦ Dérive           ✓  4 variables dérivées · marchand     ← votre atelier 3

Pipeline terminé — 7 étapes, 3.9 s au total.
```

**Remettez `seuil_f1: 0.95` dans `params.yaml` et relancez** : le pipeline
s'arrête à l'étape 5, en rouge. C'est la même porte de qualité que celle qui a
fait rougir votre CI à l'atelier 1 — vue autrement.

Les trois autres onglets sont là pour explorer :

| Onglet | Ce qu'il fait |
|---|---|
| **Inférence** | scorer une transaction à la main, ou un fichier entier — essayez `type_contrepartie: marchand` |
| **Monitoring** | l'état des services et le rapport de dérive |
| **Journal** | tout ce que vos commandes ont écrit dans `logs/lab.log` |

---

## Pour aller plus loin, chez vous

Ce lab laisse un trou volontaire : **`reports/metriques.json` est écrasé à chaque
entraînement.** Vous ne pouvez comparer aucun modèle au précédent. Aucun des
trois ateliers ne le comble.

Le dépôt contient **MLflow déjà installé et configuré** pour ça. Rien à coder,
rien à brancher — c'est là si vous voulez l'essayer chez vous :

```bash
pip install -r requirements-plus-loin.txt
docker compose --profile plus-loin up -d --build
```

L'interface est sur <http://localhost:5001>. Pour enregistrer un entraînement :

```bash
MLFLOW_TRACKING_URI=http://localhost:5001 python -m src.train
```

Changez `n_estimators` dans `params.yaml`, relancez, et comparez les deux runs
côte à côte dans l'interface. C'est exactement ce que le lab ne sait pas faire.

Le serveur MLflow est **sous profil Docker** : un `docker compose up -d` normal
ne le démarre pas, et sans la variable `MLFLOW_TRACKING_URI` l'entraînement se
comporte comme d'habitude. Vous ne risquez rien à essayer.

Les détails sont dans le README, section *Suivi d'expériences avec MLflow*.

---

## Arrêter la pile

Quand vous avez fini :

```bash
docker compose down
```

---

## Les trois questions du lab, en une phrase chacune

| Atelier | La question | Ce que vous avez vu |
|---|---|---|
| 1 | Est-ce assez bon ? | Une chaîne qui refuse un modèle et dit pourquoi |
| 2 | Quelle version répond en production ? | Le label `version_modele` sur chaque métrique |
| 3 | Est-ce encore vrai ? | Un modèle correct sur 2025, faux sur une population de 2026 |
