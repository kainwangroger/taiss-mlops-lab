# Atelier 2 — Instrumenter votre API

**15 minutes · ensemble, étape par étape**

Votre service répond, mais personne ne sait ce qu'il répond. Vous allez lui
ajouter trois compteurs, lancer la pile de monitoring, et voir vos propres
prédictions défiler dans un tableau de bord.

---

## Étape 1 — Ouvrir le fichier du service

Ouvrez `src/serve.py` dans votre éditeur. Vous allez y faire **trois
remplacements**, dans l'ordre.

Vous vérifierez votre travail à l'étape 7, directement sur `/metrics`, et à
l'étape 9 dans Grafana.

---

## Étape 2 — Remplacer la ligne d'import

Cherchez cette ligne, vers le haut du fichier :

```python
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
```

Remplacez-la par celle-ci :

```python
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
```

---

## Étape 3 — Déclarer les trois métriques

Cherchez le grand bloc de commentaires qui commence par
`# ATELIER 2 — étape 1 : déclarer les métriques`. Il est encadré par deux lignes
de `# =====`.

**Supprimez tout ce bloc, des `# =====` du haut aux `# =====` du bas inclus**, et
collez ceci à la place :

```python
# =============================================================================
# Les métriques exposées à Prometheus.
#
#   Counter   ce qui ne fait que monter        -> nombre de prédictions
#   Histogram une distribution de valeurs      -> latence d'inférence
#   Gauge     une valeur qui monte et descend  -> score moyen glissant
#
# Toutes portent le label version_modele. Sans lui, impossible de comparer un
# champion et un challenger, ni d'imputer une dégradation à un déploiement.
# =============================================================================
PREDICTIONS = Counter(
    "predictions_total",
    "Nombre de prédictions servies",
    ["version_modele", "classe"],
)
LATENCE = Histogram(
    "inference_secondes",
    "Latence d'inférence",
    ["version_modele"],
)
SCORE_MOYEN = Gauge(
    "score_moyen_glissant",
    "Score de fraude moyen sur les 200 dernières prédictions",
    ["version_modele"],
)
CATEGORIE_INCONNUE = Counter(
    "categorie_inconnue_total",
    "Requêtes portant une catégorie absente du jeu d'entraînement",
    ["version_modele", "colonne"],
)
```

---

## Étape 4 — Remplacer la fonction de prédiction

Cherchez la ligne `@app.post("/predict")`. **Supprimez tout depuis cette ligne
jusqu'à l'accolade fermante `}` qui termine la fonction**, juste avant
`@app.get("/metrics")`.

Collez ceci à la place :

```python
@app.post("/predict")
def predire(transaction: Transaction):
    modele = charger_modele()
    debut = time.perf_counter()

    df = pd.DataFrame([transaction.model_dump()])

    # Une catégorie inconnue ne fait pas planter le service : elle le fait se
    # tromper en silence. On la compte, faute de pouvoir la refuser.
    if transaction.type_contrepartie not in CATEGORIES_CONNUES:
        CATEGORIE_INCONNUE.labels(VERSION_MODELE, "type_contrepartie").inc()

    score = float(modele.predict_proba(construire_features(df))[0][1])
    signalee = int(score >= SEUIL_DECISION)
    duree = time.perf_counter() - debut

    LATENCE.labels(VERSION_MODELE).observe(duree)
    PREDICTIONS.labels(VERSION_MODELE, "signalee" if signalee else "normale").inc()

    _derniers_scores.append(score)
    del _derniers_scores[:-200]
    SCORE_MOYEN.labels(VERSION_MODELE).set(
        sum(_derniers_scores) / len(_derniers_scores)
    )

    return {
        "score": round(score, 4),
        "signalee": bool(signalee),
        "seuil_decision": SEUIL_DECISION,
        "version_modele": VERSION_MODELE,
        "latence_ms": round(duree * 1000, 2),
    }
```

Enregistrez le fichier.

---

## Étape 5 — Vérifier par les tests

```bash
python -m pytest tests/ -q
python -m ruff check src tests
```

**Vous devez voir :**

```text
27 passed in 3.4s
All checks passed!
```

**27, plus aucun test ignoré.** Le test `test_les_metriques_metier_sont_exposees`
était en attente depuis le début de la séance : il passe maintenant.

---

## Étape 6 — Lancer la pile de monitoring

```bash
docker compose up -d --build
```

La première construction prend quelques minutes.

**Vous devez voir**, à la fin :

```text
 ✔ Container taiss-api         Started
 ✔ Container taiss-prometheus  Started
 ✔ Container taiss-grafana     Started
```

Trois conteneurs tournent :

| Service | Adresse |
|---|---|
| API | <http://localhost:8001/docs> |
| Prometheus | <http://localhost:9091> |
| Grafana | <http://localhost:3002> |

Ouvrez <http://localhost:9091/targets>.

**Vous devez voir** une cible `api-fraude` avec l'état **UP** en vert. Si elle
est rouge, l'API n'a pas démarré : dites-le maintenant.

---

## Étape 7 — Envoyer une première prédiction

```bash
curl -X POST http://localhost:8001/predict \
  -H "Content-Type: application/json" \
  -d '{"montant":45000,"heure":21,"frequence_7j":4,"anciennete_jours":35,"type_contrepartie":"particulier"}'
```

Sous Windows, `curl` n'accepte pas ces options. Utilisez :

```powershell
$corps = @{
  montant = 45000
  heure = 21
  frequence_7j = 4
  anciennete_jours = 35
  type_contrepartie = "particulier"
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:8001/predict `
  -Method Post -ContentType "application/json" -Body $corps
```

**Vous devez voir :**

```json
{"score":0.9569,"signalee":true,"seuil_decision":0.45,"version_modele":"fraude-v1","latence_ms":45.8}
```

Ouvrez maintenant <http://localhost:8001/metrics> dans votre navigateur et
cherchez `predictions_total`.

**Vous devez voir :**

```text
# TYPE predictions_total counter
predictions_total{classe="signalee",version_modele="fraude-v1"} 1.0
```

**Le `version_modele="fraude-v1"` est le point de tout l'atelier.** Sans ce
label, vous sauriez qu'il y a eu une prédiction, mais pas quelle version du
modèle l'a produite.

---

## Étape 8 — Générer du trafic

```bash
python -m src.replay --n 500 --url http://localhost:8001
```

**Vous devez voir**, à la fin :

```text
500 prédictions en 25.8 s (19 req/s)
score moyen        : 0.0122
taux de signalement: 0.60%
```

Le débit dépend de votre machine, pas le taux de signalement.

**Notez ce chiffre : 0,60 % de transactions signalées.** Vous en aurez besoin à
l'atelier 3.

---

## Étape 9 — Regarder le tableau de bord

Ouvrez <http://localhost:3002>.

Le tableau de bord est déjà construit, vous n'avez rien à faire. Menu
**Dashboards** → dossier *TAISS 2026* → **TAISS 2026 — Détection de fraude**.

**Vous devez voir** quatre courbes qui se remplissent : le débit, la latence, le
score moyen, et le taux de signalement autour de 1 %.

Retournez sur <http://localhost:8001/metrics> et cherchez vos trois métriques :

```text
predictions_total{classe="signalee",version_modele="fraude-v1"} 4.0
predictions_total{classe="normale",version_modele="fraude-v1"} 497.0
inference_secondes_count{version_modele="fraude-v1"} 501.0
score_moyen_glissant{version_modele="fraude-v1"} 0.00815050992245
```

501 prédictions : les 500 du rejeu, plus celle que vous avez envoyée à la main.
La jauge, elle, ne vaut pas la moyenne du rejeu — c'est une moyenne **glissante
sur les 200 dernières**, et c'est voulu : une moyenne depuis le démarrage cesse
de bouger après quelques milliers de requêtes, et ne montrerait donc rien à
l'atelier 3.

**Les trois primitives sont là, et toutes portent `version_modele`.** Avant
l'étape 4, cette page ne contenait que les métriques par défaut du processus
Python : le service répondait, mais il n'était pas observable.

---

## Étape 10 — Taguer l'image avec le commit

```bash
docker build -t fraude:$(git rev-parse --short HEAD) .
docker images | grep fraude
```

**Vous devez voir :**

```text
fraude    a3f9c21    d4e8b1a09c77   12 seconds ago   1.24GB
```

`a3f9c21` est le début du hash de votre commit. Cette image contient exactement
le code de ce commit-là, et son modèle. C'est ce qui permet d'y revenir : si la
version suivante se comporte mal, une seule commande relance celle-ci.

---

## L'atelier 2 est terminé

Vous avez :

- [x] rendu votre service observable avec trois métriques ;
- [x] étiqueté chaque métrique par version de modèle ;
- [x] vu vos propres prédictions arriver dans Grafana ;
- [x] produit une image identifiée par son commit.

`/metrics` expose vos trois métriques, et Grafana les affiche.

---

## Si ça bloque

| Ce que vous voyez | Ce qu'il faut faire |
|---|---|
| `NameError: name 'Counter' is not defined` | L'étape 2 n'est pas faite : la ligne d'import n'a pas été remplacée |
| `port is already allocated` | `docker compose down`, puis relancez `docker compose up -d --build` |
| La cible Prometheus est rouge | L'API n'a pas démarré : `docker compose logs api` |
| Le tableau de bord est vide | Aucun trafic généré : refaites l'étape 8 |
| `/metrics` ne contient pas `predictions_total` | Le conteneur tourne avec l'ancien code : relancez avec `--build` |
| `Connection refused` au replay | La pile n'est pas lancée, ou vous avez oublié `--url http://localhost:8001` |
| Grafana demande un mot de passe | `admin` / `admin` |

---

## La question à se poser

Votre tableau de bord montre la latence, le débit et le taux de signalement.
**Aucune de ces courbes ne dit si le modèle a raison.** Pourquoi ? Et que
faudrait-il pour le savoir ?

---

**Suite** → [Atelier 3 — Voir la dérive](ATELIER-3.md)
