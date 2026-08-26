# taiss-mlops-lab

Détecteur de fraude sur des transactions mobile money, avec la chaîne MLOps
complète autour : tests de données, porte de qualité, intégration continue,
API instrumentée, monitoring et détection de dérive.

Support de travaux pratiques de la **Togo AI Summer School 2026**, filière F3 —
Data Engineering & MLOps.

---

## Le problème

Un modèle est entraîné sur le trafic mobile money de 2025. Six mois plus tard,
l'opérateur lance le paiement marchand : une population de transactions que le
modèle n'a jamais vue apparaît en production. Le code n'a pas changé, les
métriques d'entraînement non plus — et pourtant le modèle se trompe.

Ce dépôt contient tout ce qu'il faut pour détecter ça avant que ça ne coûte
cher.

---

## Installation

Python 3.11 et Docker sont requis.

```bash
git clone https://github.com/kainwangroger/taiss-mlops-lab.git
cd taiss-mlops-lab

python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate

pip install -r requirements.txt
pip install -r requirements-console.txt
```

Vérifiez que tout fonctionne :

```bash
python -m src.train
```

Le F1 attendu est **0.7273**. Une autre valeur signale une version de
bibliothèque qui a bougé — les versions sont épinglées dans
`requirements.txt` pour cette raison.

---

## Utilisation

### Entraîner et évaluer

```bash
python -m src.train        # entraîne, écrit models/modele.pkl et reports/metriques.json
python -m src.evaluate     # compare aux seuils de params.yaml, sort en code 0 ou 1
python -m pytest tests/ -q
python -m ruff check src tests
```

`src/evaluate.py` est la porte de qualité : c'est le seul endroit du projet qui
peut dire non. Elle sort en code 1 quand le F1 passe sous le seuil, ce qui fait
échouer la chaîne d'intégration.

### Lancer le service seul

```bash
python -m uvicorn src.serve:app --host 0.0.0.0 --port 8000
```

L'API expose `POST /predict`, `GET /health` et `GET /metrics`.
Documentation interactive sur <http://localhost:8000/docs>.

### Lancer toute la pile

```bash
docker compose up -d --build
```

| Service | Adresse |
|---|---|
| API | <http://localhost:8001/docs> |
| Prometheus | <http://localhost:9091> |
| Grafana | <http://localhost:3002> |

Deux services supplémentaires sont sous profil et ne démarrent qu'à la demande :

```bash
docker compose --profile plateforme up -d --build   # la plateforme, port 8502
docker compose --profile plus-loin up -d --build    # MLflow, port 5001
```

```bash
docker compose down
```

### Générer du trafic et mesurer la dérive

```bash
# trafic normal — taux de signalement attendu : 0,60 %
python -m src.replay --n 500 --url http://localhost:8001

# trafic 2026 — taux de signalement attendu : 15,00 %
python -m src.replay --input data/drifted_2026.csv --n 800 --url http://localhost:8001

python -m src.drift_report     # écrit reports/derive.html
```

### La plateforme

**Hors ateliers.** Une application Streamlit qui fait en un clic ce que les
commandes ci-dessus font une par une, et qui montre le pipeline s'exécuter.
Les ateliers ne l'utilisent pas : ils font tout à la main, c'est le sujet. Elle
sert à voir l'ensemble une fois les trois ateliers terminés.

```bash
python -m streamlit run src/console.py --server.port 8501
```

| Onglet | Ce qu'il fait |
|---|---|
| **Pipeline** | exécute les sept étapes — chargement, contrat, prétraitement, entraînement, porte de qualité, prédiction, dérive — et allume le graphe au fur et à mesure. Une étape qui échoue arrête la suite |
| **Inférence** | score une transaction saisie à la main, ou un fichier entier ; passe par l'API si elle répond, sinon par le modèle local |
| **Monitoring** | état des services, métriques réellement exposées par `/metrics`, rapport de dérive et analyse par segment |
| **Journal** | `logs/lab.log`, filtrable par source et par niveau |

Elle occupe son terminal tant qu'elle tourne. En conteneur, il faut la demander :
`docker compose --profile plateforme up -d --build`, puis <http://localhost:8502>.

### Le journal

Tout ce que produisent l'entraînement, la porte de qualité, le rejeu, le rapport
de dérive et le service converge dans un seul fichier.

```bash
tail -n 40 logs/lab.log                    # Windows : Get-Content logs\lab.log -Tail 40
```

### Raccourcis

Les mêmes commandes sont disponibles via `make` (Linux, macOS) et `lab.ps1`
(Windows) : `train`, `test`, `lint`, `serve`, `console`, `up`, `replay`,
`drift`, `logs`, `down`, `clean`.

```bash
make train
```

```powershell
.\lab.ps1 train
```

---

## Les travaux pratiques

Trois ateliers, deux heures, à faire dans l'ordre. Chaque étape donne la
commande à taper et le résultat attendu.

| | Atelier | Durée | Ce que vous produisez |
|---|---|---|---|
| 1 | [Du commit à la CI verte](docs/ATELIER-1.md) | 20 min | Une chaîne d'intégration qui refuse un modèle insuffisant |
| 2 | [Instrumenter votre API](docs/ATELIER-2.md) | 15 min | Un tableau de bord où vos prédictions défilent en temps réel |
| 3 | [Voir la dérive](docs/ATELIER-3.md) | 15 min | Un rapport qui montre le modèle décrocher, et une décision |

---

## Structure du projet

```
taiss-mlops-lab/
├── params.yaml                 tous les paramètres — aucune valeur en dur ailleurs
├── requirements.txt            versions épinglées
├── requirements-console.txt    la plateforme (Streamlit), séparée pour ne pas alourdir la CI
├── requirements-plus-loin.txt  MLflow, optionnel
│
├── Dockerfile                  l'image du service
├── Dockerfile.console          l'image de la plateforme, sous profil
├── Dockerfile.mlflow           le serveur MLflow, sous profil
├── docker-compose.yml          la pile complète
├── Makefile · lab.ps1          les raccourcis
│
├── data/
│   ├── generate_data.py        génère les deux jeux, de façon reproductible
│   ├── reference_2025.csv      trafic d'entraînement — 20 000 lignes
│   └── drifted_2026.csv        trafic dérivé — 8 000 lignes
│
├── src/
│   ├── features.py             transformations + contrat de données (CONTRAT)
│   ├── train.py                entraînement
│   ├── evaluate.py             porte de qualité — sort en code 1
│   ├── serve.py                API FastAPI
│   ├── replay.py               rejoue du trafic contre le service
│   ├── drift_report.py         PSI, Kolmogorov–Smirnov, khi-deux → rapport HTML
│   ├── console.py              la plateforme Streamlit — pipeline, inférence, monitoring
│   ├── journal.py              tout converge vers logs/lab.log
│   └── suivi.py                suivi MLflow, optionnel
│
├── tests/
│   ├── test_features.py        unitaires
│   ├── test_data_contract.py   contrat de données
│   ├── test_model_quality.py   qualité du modèle
│   └── test_api.py             intégration du service
│
├── monitoring/
│   ├── prometheus.yml          la cible à collecter
│   └── grafana/                2 tableaux de bord + règles d'alerte, provisionnés
├── .github/workflows/ci.yml    la chaîne d'intégration
└── docs/                       les trois ateliers
```

---

## La chaîne d'intégration

`.github/workflows/ci.yml` se déclenche sur un push vers `main`, sur une pull
request vers `main`, et chaque lundi à 3 h.

```
ruff → tests unitaires → contrat de données → entraînement
     → porte de qualité → tests d'API → artefact modele-<sha>
     → construction de l'image (uniquement si tout est vert, et sur main)
```

Le job qui construit l'image dépend du job de qualité. **Un modèle qui ne passe
pas la porte ne produit pas d'image.**

---

## Choix techniques

**Les données sont synthétiques.** Elles reproduisent la structure d'un jeu de
transactions mobile money sans en être un. La dérive de 2026 est injectée
délibérément, de trois natures : dérive des distributions, apparition d'une
catégorie inconnue, et changement de la relation entre les variables et la
fraude. C'est la troisième qui rend le réentraînement naïf inefficace.

**Le rapport de dérive n'utilise aucune bibliothèque d'observabilité.** PSI,
Kolmogorov–Smirnov et khi-deux sont calculés dans `src/drift_report.py` avec
numpy, pandas et scipy. L'API des outils du domaine change entre versions
majeures ; un atelier de quinze minutes ne peut pas en dépendre.

**Les versions sont épinglées.** Ne les élargissez pas sans rejouer les trois
ateliers de bout en bout sur une machine vierge.

**La console et MLflow sont isolés du pipeline.** Streamlit et MLflow vivent
dans leurs propres fichiers de dépendances et leurs propres images. Ni la
chaîne d'intégration ni l'image du service ne les installent.

---

## Pour aller plus loin — suivi d'expériences avec MLflow

**Hors ateliers, à essayer chez vous.** Le lab laisse un trou volontaire :
`reports/metriques.json` est écrasé à chaque entraînement, donc comparer deux
modèles est impossible. MLflow est déjà installé et configuré dans ce dépôt pour
combler ce trou — il n'y a rien à coder.

Le serveur est sous profil Docker — `docker compose up -d` ne le démarre pas.

```bash
pip install -r requirements-plus-loin.txt
docker compose --profile plus-loin up -d --build
```

L'interface est sur <http://localhost:5001>. Pour enregistrer un entraînement :

```bash
MLFLOW_TRACKING_URI=http://localhost:5001 python -m src.train
```

```powershell
$env:MLFLOW_TRACKING_URI = "http://localhost:5001"
python -m src.train
```

Le run contient les paramètres, les métriques, le verdict de la porte de qualité
et le pipeline scikit-learn complet en artefact. Changez `n_estimators` dans
`params.yaml`, relancez, et comparez les deux runs dans l'interface.

**Sans la variable `MLFLOW_TRACKING_URI`, `src/train.py` se comporte exactement
comme avant.** C'est nécessaire : il tourne aussi pendant la construction de
l'image Docker et dans la chaîne d'intégration, deux contextes sans serveur
MLflow. Un suivi d'expériences qui fait échouer un build est pire que pas de
suivi du tout.

---

## Licence

Matériel pédagogique du Togo AI Lab, réutilisable et modifiable pour tout usage
de formation. Voir [LICENSE](LICENSE).
