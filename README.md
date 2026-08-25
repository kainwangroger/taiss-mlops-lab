# Lab MLOps — CI/CD et monitoring

**Togo AI Summer School 2026 · Filière F3 — Data Engineering & MLOps**
Jeudi 27 août 2026 · 13:00 – 15:00 · Bloc A

Encadrants : BESSAN Olivier · KAINWANG Roger · ATARMLA Abdou-Raouf

---

## Ce que vous allez construire

Un détecteur de fraude sur des transactions mobile money, entraîné sur le trafic
de 2025 — puis tout ce qu'il faut autour pour lui faire confiance six mois plus
tard.

En deux heures, trois ateliers :

| | Atelier | Ce que vous produisez |
|---|---|---|
| 1 | Du commit à la CI verte | Une chaîne d'intégration qui refuse une fusion quand le modèle n'est pas assez bon |
| 2 | Instrumenter votre API | Un tableau de bord où vos propres prédictions défilent en temps réel |
| 3 | Voir la dérive | Un rapport qui montre le modèle en train de décrocher, et une décision argumentée |

Le service et le `Dockerfile` de ce dépôt sont ceux que vous avez produits
mercredi. Nous ne parachutons rien : nous ajoutons trois dossiers à votre
travail — `tests/`, `.github/workflows/` et `monitoring/`.

---

## À faire avant d'arriver

```bash
# 1. Forkez ce dépôt sur votre compte GitHub, puis :
git clone https://github.com/VOTRE-COMPTE/taiss-mlops-lab.git
cd taiss-mlops-lab

# 2. L'environnement (Python 3.11 requis)
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt

# 3. Le test de fumée — il doit se terminer par « OK »
make smoke
```

Vérifiez aussi que Docker démarre :

```bash
docker --version
docker compose version
docker run --rm hello-world
```

Sous Windows, installez [Docker Desktop](https://www.docker.com/products/docker-desktop/),
activez le moteur WSL 2 recommande, demarrez Docker Desktop, puis rouvrez
PowerShell.

Sous Ubuntu/Debian, installez Docker Engine et le plugin Compose depuis le
depot officiel Docker. La procedure detaillee et les commandes de verification
sont dans `MISE-EN-LIGNE.md`.

Si l'une de ces étapes échoue, **ne cherchez pas à la résoudre seul** :
signalez-le et venez quand même, nous prévoyons du binômage.

> **Activez les Actions sur votre fork.** GitHub les désactive par défaut.
> Onglet **Actions** de votre fork, puis le bouton d'activation. Sans cela,
> l'atelier 1 ne se déclenchera jamais.

---

## Les commandes

```bash
make smoke      # vérifie que votre poste est prêt
make train      # entraîne le modèle
make test       # toute la suite de tests
make lint       # style
make serve      # API seule, sur le port 8000
make up         # API + Prometheus + Grafana        (atelier 2)
make replay     # rejoue du trafic normal           (atelier 2)
make drift      # rejoue le trafic 2026 + rapport   (atelier 3)
make down       # arrête tout
```

Pour utiliser `replay` sans Docker, demarrez d'abord l'API dans un terminal :

```bash
python -m uvicorn src.serve:app --host 127.0.0.1 --port 8000
```

Puis, dans un second terminal :

```bash
python -m src.replay --n 500
```

Avec Docker Compose, l'API est exposee sur le port `8001` :

```bash
docker compose up -d --build
python -m src.replay --url http://localhost:8001 --n 500
```

Pour l'atelier 3, rejouez le trafic derive 2026 sur la meme API Docker :

```powershell
python -m src.replay `
    --url http://localhost:8001 `
    --input data/drifted_2026.csv `
    --n 800
```

Si `replay` affiche `Connection refused` ou `WinError 10061`, aucun service
n'ecoute sur l'URL utilisee. Verifiez d'abord :

```bash
curl http://localhost:8000/health
```

Sous PowerShell, utilisez `Invoke-RestMethod http://localhost:8000/health`.
Les tests `pytest` peuvent pourtant passer, car ils testent l'application
directement et ne demarrent pas de serveur HTTP.

| Service | Adresse |
|---|---|
| API (documentation interactive) | <http://localhost:8001/docs> |
| Métriques brutes | <http://localhost:8001/metrics> |
| Prometheus | <http://localhost:9091> |
| Grafana | <http://localhost:3002> |

---

## Le dépôt

```
taiss-mlops-lab/
├── params.yaml                 tous les paramètres — aucune valeur en dur ailleurs
├── Makefile                    les commandes du lab
├── Dockerfile                  ← votre travail de mercredi
├── docker-compose.yml          la pile de monitoring
│
├── data/
│   ├── generate_data.py        génère les deux jeux, de façon reproductible
│   ├── reference_2025.csv      le trafic d'entraînement
│   └── drifted_2026.csv        le trafic dérivé de l'atelier 3
│
├── src/
│   ├── features.py             transformations + contrat de données
│   ├── train.py                entraînement
│   ├── evaluate.py             porte de qualité — c'est elle qui dit non
│   ├── serve.py                ← votre API de mercredi, à instrumenter
│   ├── replay.py               rejoue du trafic contre le service
│   └── drift_report.py         PSI, Kolmogorov–Smirnov, khi-deux → rapport HTML
│
├── tests/
│   ├── test_features.py        étage 1 — unitaires
│   ├── test_data_contract.py   étage 2 — contrat de données  (à compléter)
│   ├── test_model_quality.py   étage 3 — qualité du modèle
│   └── test_api.py             étage 4 — intégration du service
│
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/                tableau de bord pré-provisionné
│
├── .github/workflows/ci.yml    la chaîne d'intégration
└── docs/
    ├── ATELIER-1.md
    ├── ATELIER-2.md
    └── ATELIER-3.md
```

---

## Les quatre questions

Elles structurent toute la séance. Chaque atelier répond à l'une d'elles.

| Pratique | La question | L'atelier |
|---|---|---|
| Versioning | Quelle version répond en production ? | 1 et 2 |
| Intégration continue | Est-ce assez bon ? | 1 |
| Livraison continue | Comment revient-on en arrière ? | 2 |
| Monitoring | Est-ce encore vrai ? | 3 |

---

## Notes techniques

**Les données sont synthétiques.** Elles reproduisent la structure d'un jeu de
transactions mobile money sans en être un. La dérive de 2026 est injectée
délibérément et de trois natures différentes : dérive des distributions,
apparition d'une catégorie inconnue, et changement de la relation entre les
variables et la fraude. C'est la troisième qui rend le réentraînement naïf
inefficace — et c'est le cœur de l'atelier 3.

**Le rapport de dérive n'utilise pas de bibliothèque externe.** PSI,
Kolmogorov–Smirnov et khi-deux sont calculés dans `src/drift_report.py` avec
numpy, pandas et scipy. C'est un choix délibéré : l'API des outils
d'observabilité change entre versions majeures, et un atelier de dix minutes ne
peut pas dépendre de cela. Si vous voulez explorer Evidently ou un équivalent
après le lab, la structure du rapport vous donnera les repères.

**Les versions sont épinglées** dans `requirements.txt`. Ne les élargissez pas
sans rejouer les trois ateliers de bout en bout.

---

## Pour aller plus loin

- `DataTalksClub/mlops-zoomcamp` — cours complet, gratuit, en auto-formation
- `evidentlyai/community-examples` — exemples d'observabilité maintenus par l'éditeur
- `fuzzylabs/evidently-monitoring-pattern` — une pile de monitoring temps réel proche de la nôtre
- Sculley et al., *Hidden Technical Debt in Machine Learning Systems*, NeurIPS 2015
- Google Cloud, *MLOps: Continuous delivery and automation pipelines in ML*

---

## Licence

Matériel pédagogique du Togo AI Lab, réutilisable et modifiable pour tout usage
de formation.
