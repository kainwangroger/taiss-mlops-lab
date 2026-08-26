# Atelier 1 — Du commit à la CI verte

**20 minutes · ensemble, étape par étape**

Vous allez écrire un contrôle qui empêche une mauvaise donnée d'entrer dans le
système, puis voir une chaîne d'intégration refuser un modèle qui n'est pas
assez bon.

> Sous Windows, les commandes `python`, `git` et `docker` sont identiques.
> Seule `Get-Content` remplace `tail` — c'est signalé là où ça arrive.

---

## Étape 1 — Installer les dépendances

Ouvrez un terminal dans le dossier du projet.

```bash
python -m venv .venv
source .venv/bin/activate
```

Sous Windows :

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Puis, dans les deux cas :

```bash
pip install -r requirements.txt
```

**Vous devez voir**, à la fin :

```text
Successfully installed ... pandas-2.2.3 ... scikit-learn-1.5.2 ... fastapi-0.115.6 ...
```

Votre invite de commande commence maintenant par `(.venv)`. Si ce n'est pas le
cas, l'environnement n'est pas activé : reprenez la commande `activate`.

---

## Étape 2 — Entraîner le modèle

```bash
python -m src.train
```

**Vous devez voir :**

```text
Modèle entraîné et sauvegardé dans models/modele.pkl
  f1               0.7273
  precision        0.6667
  rappel           0.8
  roc_auc          0.9963
  seuil_decision   0.45
  version_modele   fraude-v1
  n_entrainement   15000
  n_test           5000
```

**Le F1 doit être exactement 0.7273.** Si vous avez autre chose, signalez-le
maintenant.

## Étape 3 — Constater ce qui manque

```bash
python -m pytest tests/test_data_contract.py -q
```

**Vous devez voir :**

```text
...sss                                                          [100%]
3 passed, 3 skipped in 0.42s
```

Trois tests passent, **trois sont ignorés**. Ces trois-là sont vides : ce sont
eux que vous allez écrire.

Ouvrez `tests/test_data_contract.py` et regardez le bas du fichier. Vous y
trouverez trois fonctions dont le corps est `pytest.skip(...)`.

---

## Étape 4 — Coller les trois tests

Dans `tests/test_data_contract.py`, **supprimez tout ce qui suit la ligne** :

```python
# --- À COMPLÉTER pendant l'atelier 1 -----------------------------------------
```

et collez ceci à la place :

```python
def test_les_categories_sont_celles_du_contrat(donnees):
    """C'est ce test qui aurait détecté l'arrivée de la catégorie « marchand »."""
    for colonne, regle in CONTRAT.items():
        if regle["type"] != "categoriel":
            continue
        observees = set(donnees[colonne].dropna().unique())
        autorisees = set(regle["categories"])
        inconnues = observees - autorisees
        assert not inconnues, (
            f"{colonne} contient des catégories absentes du contrat : "
            f"{sorted(inconnues)}. Catégories autorisées : {sorted(autorisees)}"
        )


def test_les_types_sont_numeriques(donnees):
    """Une colonne montant arrivant en texte est un incident classique."""
    from pandas.api.types import is_numeric_dtype

    for colonne, regle in CONTRAT.items():
        if regle["type"] != "numerique":
            continue
        assert is_numeric_dtype(donnees[colonne]), (
            f"{colonne} devrait être numérique, "
            f"type observé : {donnees[colonne].dtype}"
        )


def test_la_cible_est_binaire_et_rare(donnees):
    """Un taux de fraude à 40 % ne signale pas une vague de fraude, mais une erreur amont."""
    valeurs = set(donnees[CIBLE].unique())
    assert valeurs <= {0, 1}, (
        f"la cible doit être binaire, valeurs observées : {sorted(valeurs)}"
    )

    taux = donnees[CIBLE].mean()
    assert 0.001 <= taux <= 0.05, (
        f"taux de fraude implausible : {taux:.2%}. "
        "En dessous de 0,1 % ou au-dessus de 5 %, suspectez une erreur en amont."
    )
```

Enregistrez le fichier.

**Ce que fait chacun**, en une phrase :

| Test | Ce qu'il attrape |
|---|---|
| `test_les_categories_sont_celles_du_contrat` | une valeur jamais vue à l'entraînement — comme `marchand`, que vous rencontrerez à l'atelier 3 |
| `test_les_types_sont_numeriques` | une colonne `montant` qui arrive en texte parce que la source a changé de format |
| `test_la_cible_est_binaire_et_rare` | un taux de fraude à 40 %, qui signale une erreur de jointure, pas une vague de fraude |

---

## Étape 5 — Relancer les tests

```bash
python -m pytest tests/test_data_contract.py -q
```

**Vous devez voir :**

```text
......                                                          [100%]
6 passed in 0.44s
```

Six points, plus aucun `s`. Puis toute la suite :

```bash
python -m pytest tests/ -q
```

**Vous devez voir :**

```text
26 passed, 1 skipped in 3.1s
```

Le dernier test ignoré est celui des métriques : c'est l'atelier 2.

Vérifiez enfin que la porte de qualité est franchie :

```bash
python -m src.evaluate
```

**Vous devez voir :**

```text
Modèle fraude-v1 — seuil de décision 0.45
métrique        obtenu     exigé   verdict
----------------------------------------------
f1              0.7273    0.6000   OK
rappel          0.8000    0.4500   OK
----------------------------------------------
Tous les seuils sont tenus. La fusion est autorisée.
```

**Retenez cette commande.** C'est elle qui va dire non dans deux étapes.

---

## Étape 6 — Envoyer sur GitHub

Jusqu'ici tout était local. On passe sur GitHub.

```bash
git add tests/test_data_contract.py
git commit -m "Completer le contrat de donnees"
git push
```

Sur GitHub, ouvrez votre dépôt et cliquez sur l'onglet **Actions**.

**Vous devez voir** un run `ci-mlops` qui démarre **tout seul**, sans que
personne ne l'ait lancé. Cliquez dessus et regardez les étapes :

```text
✔ Vérifier le style
✔ Tests unitaires du code
✔ Contrat de données          ← les trois tests que vous venez d'écrire
✔ Entraîner le modèle
✔ Porte de qualité du modèle
✔ Tests d'intégration de l'API
✔ Publier le modèle et les métriques
```

Au bout de deux à trois minutes : **pastille verte**.

En bas de la page du run, section *Artifacts*, il y a un fichier
`modele-<sha>` téléchargeable. C'est le modèle que la chaîne a entraîné.

---

## Étape 7 — Faire échouer la chaîne

C'est l'étape la plus importante de l'atelier.

Ouvrez `params.yaml`. Trouvez la ligne `seuil_f1: 0.60` et remplacez-la par :

```yaml
  seuil_f1: 0.95
```

Puis :

```bash
git commit -am "Monter le seuil a 0.95"
git push
```

Retournez dans l'onglet **Actions**. Un nouveau run démarre.

**Vous devez voir** une **pastille rouge**. Ouvrez le run, puis l'étape
*Porte de qualité du modèle* :

```text
métrique        obtenu     exigé   verdict
----------------------------------------------
f1              0.7273    0.9500   ÉCHEC
rappel          0.8000    0.4500   OK
----------------------------------------------
ÉCHEC : le seuil « f1 » n'est pas tenu — 0.7273 obtenu, 0.9500 exigé.
La fusion est refusée. Corrigez le modèle ou justifiez le seuil.
```

**Regardez maintenant la liste des jobs à gauche.** Le job `image`, qui
construit le conteneur, **n'a pas démarré du tout**. Il attend que la qualité
soit au vert. Un modèle refusé ne produit pas d'image.

---

## Étape 8 — Revenir au vert

Dans `params.yaml`, remettez :

```yaml
  seuil_f1: 0.60
```

```bash
git commit -am "Revenir a un seuil defendable"
git push
```

**Vous devez voir**, dans Actions : le run repasse au **vert**, et cette fois le
job `image` se lance à la suite du premier.

---

## L'atelier 1 est terminé

Vous avez :

- [x] écrit trois contrôles sur les données ;
- [x] vu une chaîne d'intégration démarrer sans que personne ne la lance ;
- [x] vu cette chaîne **dire non**, et dire pourquoi ;
- [x] vu qu'un modèle refusé ne produit pas d'image.

`python -m pytest tests/ -q` donne `26 passed, 1 skipped`, et la CI est verte.

---

## Si ça bloque

| Ce que vous voyez | Ce qu'il faut faire |
|---|---|
| `python: command not found` | Essayez `python3` |
| L'invite n'affiche pas `(.venv)` | L'environnement n'est pas activé — refaites l'étape 1 |
| `3 passed, 3 skipped` après l'étape 4 | Le fichier n'est pas enregistré, ou le code a été collé au mauvais endroit |
| Rien ne se déclenche dans Actions | Les Actions ne sont pas activées : onglet **Actions** → bouton d'activation |
| `Permission denied` au push | Vous avez cloné le dépôt d'origine, pas votre fork. Vérifiez `git remote -v` |
| `rejected — non-fast-forward` | `git pull --rebase`, puis repoussez |
| Le run reste en attente | File d'attente GitHub. Patientez, ne relancez pas en boucle |

---

## La question à se poser

Le seuil de 0,60 : **qui devrait le fixer ?** Le data scientist seul, ou le
métier avec lui ?

Un seuil à 0,95 bloque toute évolution. Un seuil à 0,50 ne protège de rien.
Entre les deux, ce n'est plus une question technique.

---

**Suite** → [Atelier 2 — Instrumenter votre API](ATELIER-2.md)
