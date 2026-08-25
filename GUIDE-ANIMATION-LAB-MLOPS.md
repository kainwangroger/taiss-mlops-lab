# Guide pas a pas — Lab MLOps CI/CD et monitoring

Ce document est le fil conducteur de la seance. Il permet de faire le TP
entier en local, puis d'utiliser GitHub uniquement pour montrer la CI.

## 0. Comprendre le scenario

Les participants construisent et surveillent un detecteur de fraude sur des
transactions mobile money :

1. le modele apprend sur le trafic 2025 ;
2. les tests controlent le code, les donnees et la qualite du modele ;
3. l'API expose les predictions ;
4. Prometheus et Grafana observent le trafic ;
5. le trafic 2026 derive et le rapport explique pourquoi le modele devient
   moins fiable.

Le point de depart de la seance est volontairement incomplet :

- trois tests du contrat de donnees sont a completer ;
- l'API repond, mais n'expose pas encore les metriques metier ;
- le modele et les metriques sont generes par `src.train`.

## 1. Preparer la machine de l'animateur

### 1.1 Ouvrir le bon dossier

Le vrai projet est le dossier imbrique suivant :

```text
lab/taiss-mlops-lab/taiss-mlops-lab
```

Depuis PowerShell :

```powershell
cd C:\Users\roger\Desktop\TAISS2026\F3_J4A_MLOps_TP\lab\taiss-mlops-lab\taiss-mlops-lab
```

### 1.2 Installer Python et les dependances

Le projet est valide avec Python 3.11. Python 3.12 fonctionne egalement dans
l'environnement local verifie, mais il est preferable d'utiliser la meme
version que la CI.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Sous Linux :

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Si Python 3.11 n'est pas disponible, Python 3.12 convient egalement :

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Si PowerShell bloque l'activation, executer une fois PowerShell en mode
utilisateur :

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 1.3 Test de fumee

Sous Windows, `make` n'est pas toujours installe. Utiliser ces commandes
Python equivalentes :

```powershell
python --version
python -c "import pandas, sklearn, fastapi, prometheus_client, yaml; print('dependances OK')"
python -c "import pandas as pd; d=pd.read_csv('data/reference_2025.csv'); print(len(d), 'lignes')"
python -m src.train
```

Sous Linux, les memes commandes s'executent depuis la racine du projet. Pour
quitter l'environnement virtuel :

```bash
deactivate
```

Resultat attendu :

```text
Modele entraine et sauvegarde dans models/modele.pkl
f1               0.7273
precision        0.6667
rappel            0.8000
roc_auc           0.9963
seuil_decision    0.45
version_modele   fraude-v1
```

## 2. Prerequis avant l'atelier 1

Avant de commencer les exercices, verifier ensemble :

- le terminal est ouvert dans `lab/taiss-mlops-lab/taiss-mlops-lab` ;
- Python 3.11 ou 3.12 est utilise ;
- l'environnement virtuel est active ;
- les dependances sont installees ;
- `data/reference_2025.csv` existe et contient 20 000 lignes ;
- `python -m src.train` produit `models/modele.pkl` ;
- Docker Desktop est demarre si l'atelier 2 doit utiliser Prometheus et Grafana ;
- les ports necessaires sont libres : 8000, 9090 et 3000, ou les ports adaptes du compose ;
- le depot Git et le remote GitHub sont optionnels pour le travail local.

Windows PowerShell :

```powershell
python --version
python -c "import pandas, sklearn, fastapi, prometheus_client, yaml; print('dependances OK')"
python -c "import pandas as pd; d=pd.read_csv('data/reference_2025.csv'); print(len(d), 'lignes')"
python -m src.train
```

Linux :

```bash
python --version
python -c "import pandas, sklearn, fastapi, prometheus_client, yaml; print('dependances OK')"
python -c "import pandas as pd; d=pd.read_csv('data/reference_2025.csv'); print(len(d), 'lignes')"
python -m src.train
```

Le resultat attendu est `dependances OK`, puis `20000 lignes` et un modele
cree dans `models/modele.pkl`. En cas d'echec, corriger ce prerequis avant de
commencer l'atelier 1.

## 3. Test local complet, sans GitHub

Cette partie est la verification minimale a faire avant la seance.

```powershell
python -m src.train
python -m src.evaluate
python -m pytest tests -q
python -m ruff check src tests
```

Resultat attendu sur la branche `main` de depart :

```text
Tous les seuils sont tenus. La fusion est autorisee.
23 passed, 4 skipped
All checks passed!
```

Les quatre tests ignores sont normaux au depart : trois tests du contrat sont
les exercices de l'atelier 1 et un test des metriques est reserve a l'atelier 2.

Le modele est valide si :

| Metrique | Obtenu | Seuil |
| -------- | -----: | ----: |
| F1       | 0,7273 |  0,60 |
| Rappel   | 0,8000 |  0,45 |
| ROC AUC  | 0,9963 | aucun |

## 4. Lancer et verifier l'API localement

Dans un terminal dedie, depuis la racine du projet :

```powershell
python -m uvicorn src.serve:app --host 127.0.0.1 --port 8000
```

Sous Linux :

```bash
python -m uvicorn src.serve:app --host 127.0.0.1 --port 8000
```

Laisser ce terminal ouvert. Dans un second terminal :

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Resultat attendu :

```json
{"statut":"ok","version_modele":"fraude-v1"}
```

Tester une prediction :

```powershell
$body = @{
  montant = 45000
  heure = 21
  frequence_7j = 4
  anciennete_jours = 35
  type_contrepartie = "particulier"
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:8000/predict `
  -Method Post -ContentType "application/json" -Body $body
```

La reponse doit contenir `score`, `signalee`, `seuil_decision` et
`version_modele`. Ouvrir aussi :

- http://localhost:8000/docs
- http://localhost:8000/metrics

Au depart, `/metrics` repond en HTTP 200 mais ne contient pas encore les
metriques metier comme `predictions_total`. C'est le point de depart de
l'atelier 2.

## 5. Atelier 1 — Contrat de donnees et CI

### Objectif a annoncer

> Avant d'entrainer ou de deployer, comment empecher une mauvaise donnee
> d'entrer dans le systeme ?

### Etape 1 — Faire constater le point de depart

```powershell
python -m pytest tests/test_data_contract.py -q
```

Resultat initial : trois tests passent et trois sont ignores. Montrer
`tests/test_data_contract.py` et les marqueurs `A COMPLETER`.

### Etape 2 — Completer les trois tests

Les participants doivent implementer :

1. les categories autorisees de `type_contrepartie` ;
2. le type numerique des colonnes numeriques ;
3. une cible binaire avec un taux de fraude entre 0,1 % et 5 %.

Le contrat de reference est dans `src/features.py`, dans `CONTRAT`.

Verification :

```powershell
python -m pytest tests/test_data_contract.py -q
```

Resultat attendu :

```text
6 passed
```

Code a copier-coller dans `tests/test_data_contract.py`, a la place des trois
fonctions marquees `À COMPLÉTER` :

```python
def test_les_categories_sont_celles_du_contrat(donnees):
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
  from pandas.api.types import is_numeric_dtype

  for colonne, regle in CONTRAT.items():
    if regle["type"] != "numerique":
      continue
    assert is_numeric_dtype(donnees[colonne]), (
      f"{colonne} devrait être numérique, "
      f"type observé : {donnees[colonne].dtype}"
    )


def test_la_cible_est_binaire_et_rare(donnees):
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

Puis relancer sous Windows ou Linux :

```text
python -m pytest tests/test_data_contract.py -q
```

Puis executer :

```powershell
python -m pytest tests -q
```

Resultat attendu apres l'atelier 1 : `26 passed, 1 skipped`.

### Etape 3 — Demonstrer la porte de qualite

Dans `params.yaml`, remplacer temporairement :

```yaml
seuil_f1: 0.60
```

par :

```yaml
seuil_f1: 0.95
```

Executer :

```powershell
python -m src.train
python -m pytest tests/test_model_quality.py -q
```

Le test doit echouer avec un message semblable a :

```text
seuil de qualite non tenu : F1 = 0.7273, seuil exige = 0.9500
```

Faire constater que la chaine sait dire non et expliquer pourquoi.

Remettre ensuite `seuil_f1: 0.60`, puis verifier a nouveau :

```powershell
python -m src.train
python -m src.evaluate
python -m pytest tests -q
```

### Etape 4 — Option GitHub

Cette etape n'est pas necessaire pour tester le projet. Elle sert a montrer la
CI distante.

```powershell
git status
git remote -v
```

Si aucun remote n'est configure, le projet est uniquement local. Pour le
publier, creer un depot GitHub vide puis :

```powershell
git remote add origin https://github.com/ORGANISATION/taiss-mlops-lab.git
git push -u origin main
```

Ensuite les participants peuvent creer une branche, pousser leur travail et
ouvrir une Pull Request. Activer l'onglet **Actions** du depot avant le TP.

La CI execute `ruff`, les tests, l'entrainement, la porte de qualite et les
tests API. Elle publie l'artefact `modele-<sha>`.

## 6. Atelier 2 — Instrumenter l'API

### Objectif a annoncer

> Une API qui repond n'est pas encore une API exploitable : comment savoir ce
> qu'elle fait en production ?

Les modifications se font dans `src/serve.py` :

- `Counter` pour le nombre de predictions ;
- `Histogram` pour la latence ;
- `Gauge` pour le score moyen glissant ;
- compteur pour les categories inconnues.

Toutes les metriques doivent avoir le label `version_modele`.

### Etape 1 — Verifier avant modification

```powershell
Invoke-WebRequest http://localhost:8000/metrics
```

Le endpoint repond, mais les metriques metier sont absentes.

### Etape 2 — Lancer la pile Docker

Verifier Docker Desktop :

```powershell
docker version
docker compose version
docker ps
```

Puis :

```powershell
docker compose up -d --build
```

Sous Linux, utiliser les memes commandes :

```bash
docker compose up -d --build
docker compose ps
```

Verifier les conteneurs :

```powershell
docker compose ps
Invoke-RestMethod http://localhost:8000/health
```

Adresses attendues pour la pile Docker (les ports 3000, 3001 et 8000 sont
reserves par d'autres services sur cette machine) :

- API : http://localhost:8001/docs
- Prometheus : http://localhost:9091
- Grafana : http://localhost:3002

Le mapping est deja adapte dans `docker-compose.yml`. Les ports internes
restent `8000` pour l'API et `9090` pour Prometheus ; seul le port visible
depuis Windows change. Ne pas arreter un conteneur qui ne concerne pas le lab
sans verifier son usage.

### Etape 3 — Generer du trafic normal

```powershell
python -m src.replay --n 500
```

Resultat attendu :

- 500 predictions sans erreur ;
- score moyen faible ;
- taux de signalement autour de 1 % ;
- `reports/predictions.csv` cree.

Dans Grafana, le tableau de bord pre-provisionne doit afficher le trafic, la
latence, le taux de signalement et le score moyen. Si les panneaux sont vides,
verifier Prometheus sur http://localhost:9090/targets : la cible `api:8000`
doit etre `UP`.

### Etape 4 — Verifier l'atelier 2

```powershell
python -m pytest tests -q
```

Resultat attendu apres instrumentation :

```text
27 passed
```

Dans `/metrics`, rechercher notamment `predictions_total` et
`inference_secondes`.

Code a copier-coller dans `src/serve.py` pour l'instrumentation de l'atelier 2.
Remplacer la declaration des metriques et completer le corps de `predire` avec
les blocs suivants :

```python
PREDICTIONS = Counter(
  "predictions_total",
  "Nombre de prédictions servies",
  ["version_modele", "classe"],
)
LATENCE = Histogram(
  "inference_secondes",
  "Durée d'inférence en secondes",
  ["version_modele"],
)
SCORE_MOYEN = Gauge(
  "score_moyen_glissant",
  "Score moyen des 200 dernières prédictions",
  ["version_modele"],
)
CATEGORIE_INCONNUE = Counter(
  "categorie_inconnue_total",
  "Nombre de prédictions avec une catégorie inconnue",
  ["version_modele", "champ"],
)
```

Dans `predire`, ajouter avant le calcul du score :

```python
if transaction.type_contrepartie not in CATEGORIES_CONNUES:
  CATEGORIE_INCONNUE.labels(VERSION_MODELE, "type_contrepartie").inc()
```

Puis ajouter apres le calcul de `duree` :

```python
LATENCE.labels(VERSION_MODELE).observe(duree)
PREDICTIONS.labels(VERSION_MODELE, "signalee" if signalee else "normale").inc()

_derniers_scores.append(score)
del _derniers_scores[:-200]
SCORE_MOYEN.labels(VERSION_MODELE).set(
  sum(_derniers_scores) / len(_derniers_scores)
)
```

## 7. Atelier 3 — Voir la derive

### Objectif a annoncer

> Le code n'a pas change, mais le monde a change. Comment le detecter et que
> decider ?

S'assurer que la pile Docker tourne encore.

### Etape 1 — Rejouer le trafic 2026

```powershell
python -m src.replay `
  --url http://localhost:8001 `
  --input data/drifted_2026.csv `
  --n 800
```

Resultat attendu :

- 800 predictions ;
- taux de signalement autour de 15 % ;
- `reports/predictions.csv` mis a jour.

Comparer avec le trafic normal de l'atelier 2.

### Etape 2 — Produire le rapport

```powershell
python -m src.drift_report
```

Le fichier [reports/derive.html](taiss-mlops-lab/taiss-mlops-lab/reports/derive.html)
est genere. Les valeurs attendues sont proches de :

| Variable          |   PSI | Verdict                                       |
| ----------------- | ----: | --------------------------------------------- |
| type_contrepartie | 5,666 | derive averee, categorie`marchand` nouvelle |
| montant           | 0,470 | derive averee                                 |
| heure             | 0,450 | derive averee                                 |
| frequence_7j      | 0,443 | derive averee                                 |
| anciennete_jours  | 0,055 | stable                                        |

### Etape 3 — Analyse segmentee

Faire executer :

```powershell
python -c "import pandas as pd; d=pd.read_csv('reports/predictions.csv'); print(d.groupby(d.type_contrepartie == 'marchand').signalee.mean())"
```

Ordres de grandeur attendus :

| Segment     | Taux de signalement |
| ----------- | ------------------: |
| marchand    |                34 % |
| particulier |               0,8 % |
| agent       |               3,8 % |
| facture     |                 0 % |

Le signal important est que le modele n'est pas uniformement casse : le
probleme est concentre sur le nouveau segment marchand.

### Etape 4 — Faire formuler la decision

Demander une phrase commencant par :

> Lundi matin, je ... parce que ...

Faire discuter trois options :

- reentrainer, mais seulement avec des donnees 2026 correctement etiquetees ;
- ajuster le seuil, en mesurant le cout des faux positifs et faux negatifs ;
- attendre les labels, tout en instrumentant davantage le segment marchand.

La reponse reflexe « reentrainer tout de suite » doit etre questionnee : les
labels 2026 sont confirmes trois jours plus tard et la relation entre les
variables et la fraude a change chez les marchands.

## 8. Arret et nettoyage

A la fin de la demonstration Docker :

```powershell
docker compose down
```

Sous Linux :

```bash
docker compose down
```

Pour refaire le lab proprement :

```powershell
Remove-Item models\modele.pkl -ErrorAction SilentlyContinue
Remove-Item reports\metriques.json,reports\predictions.csv,reports\derive.html -ErrorAction SilentlyContinue
python -m src.train
```

Ne supprimer que les conteneurs du projet avec `docker compose down`; ne pas
utiliser de commande destructive globale sur les autres conteneurs de la
machine.

## 9. Tableau de bord de l'animateur

Avant la seance, verifier :

- [ ] le dossier de travail est bien `lab/taiss-mlops-lab/taiss-mlops-lab` ;
- [ ] Python et les dependances sont installes ;
- [ ] `python -m src.train` produit le modele ;
- [ ] `python -m src.evaluate` passe ;
- [ ] les tests initiaux donnent `23 passed, 4 skipped` ;
- [ ] Docker Desktop est demarre ;
- [ ] les ports 8000, 9090 et 3000 sont disponibles, ou le port Grafana est adapte ;
- [ ] les branches de correction sont conservees localement si elles existent ;
- [ ] le depot GitHub est publie et les Actions sont activees si la CI distante
  est prevue ;
- [ ] le scenario de panne a ete repete sur une machine vierge.

## Message simple a donner aux participants

> On ne commence pas par GitHub. On commence par faire fonctionner le projet
> localement. Ensuite on securise les donnees et la qualite du modele. Puis on
> observe l'API. Enfin on rejoue 2026 pour constater la derive et prendre une
> decision. GitHub ne sert qu'a automatiser cette verification sur une Pull
> Request.
