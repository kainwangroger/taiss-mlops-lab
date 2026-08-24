# Atelier 1 — Du commit à la CI verte

**20 minutes · en autonomie, encadrants en salle**

À la fin de cet atelier, vous aurez sur votre propre compte GitHub une chaîne
d'intégration qui refuse une fusion quand le modèle n'est pas assez bon — et
vous l'aurez vue refuser, pour de vrai.

---

## Étape 1 — Forker et cloner (2 min)

Sur la page du dépôt, cliquez sur **Fork**. Puis, en local :

```bash
git clone https://github.com/VOTRE-COMPTE/taiss-mlops-lab.git
cd taiss-mlops-lab
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make smoke
```

> **Important.** GitHub désactive les Actions par défaut sur un fork. Allez dans
> l'onglet **Actions** de votre fork et cliquez sur le bouton d'activation. Sans
> cela, rien ne se déclenchera et vous chercherez longtemps.

---

## Étape 2 — Compléter le contrat de données (6 min)

Ouvrez `tests/test_data_contract.py`. Trois tests sont déjà écrits, trois sont à
compléter. Cherchez les marqueurs `À COMPLÉTER`.

Le plus important est le premier : **les catégories**. C'est lui qui aurait
détecté l'arrivée de la catégorie `marchand` avant qu'elle n'atteigne la
production. Vous en verrez les conséquences à l'atelier 3.

Le contrat de référence est le dictionnaire `CONTRAT` dans `src/features.py`.

```bash
pytest tests/test_data_contract.py -q
```

Les trois tests doivent passer, plus aucun `skip`.

---

## Étape 3 — Ouvrir une pull request (3 min)

```bash
git checkout -b atelier-1-contrat
git add tests/test_data_contract.py
git commit -m "Compléter le contrat de données"
git push -u origin atelier-1-contrat
```

Sur GitHub, ouvrez une pull request vers `main` **de votre propre fork**.
Regardez la chaîne se déclencher dans l'onglet Actions.

---

## Étape 4 — Casser volontairement la chaîne (4 min)

C'est l'étape la plus formatrice de l'atelier. Ne la sautez pas.

Dans `params.yaml`, montez le seuil :

```yaml
evaluation:
  seuil_f1: 0.95
```

```bash
git commit -am "Monter le seuil à 0.95"
git push
```

Retournez sur la pull request. Elle doit passer au **rouge**, et le message
d'erreur doit nommer explicitement le seuil non tenu :

```
seuil de qualité non tenu : F1 = 0.7273, seuil exigé = 0.9500.
Le modèle ne peut pas être promu en l'état.
```

C'est exactement ce qu'on attend d'une porte de qualité : elle dit non, et elle
dit pourquoi.

---

## Étape 5 — Corriger et fusionner (3 min)

```yaml
evaluation:
  seuil_f1: 0.60
```

```bash
git commit -am "Revenir à un seuil défendable"
git push
```

La chaîne repasse au vert. Fusionnez.

---

## Critères de réussite

- [ ] La chaîne se déclenche automatiquement à l'ouverture de la pull request
- [ ] Les six tests de contrat passent, sans `skip`
- [ ] L'échec volontaire nomme explicitement le seuil non tenu
- [ ] Le run vert produit un artefact `modele-<sha>` téléchargeable
- [ ] La pull request est fusionnée

---

## Ce qui bloque habituellement

| Symptôme | Cause probable |
|---|---|
| Rien ne se déclenche | Les Actions ne sont pas activées sur le fork |
| `Permission denied` au push | Vous avez cloné le dépôt d'origine, pas votre fork. Vérifiez `git remote -v` |
| Le test passe en local, échoue en CI | Version de Python différente. La CI utilise 3.11 |
| Le run reste en attente | File d'attente des exécuteurs partagés. Patientez, ne relancez pas en boucle |

---

## La question à se poser

Le seuil de 0,60 : qui devrait le fixer ? Le data scientist seul, ou le métier
avec lui ? Un seuil à 0,95 bloque toute évolution. Un seuil à 0,50 ne protège de
rien. Entre les deux, ce n'est plus une question technique.
