# Atelier 2 — Instrumenter votre API

**15 minutes · en binôme**

À la fin de cet atelier, vous verrez vos propres prédictions défiler dans un
tableau de bord. C'est le moment « ça marche » de la séance.

---

## Le point de départ

`src/serve.py` est le service que vous avez conteneurisé mercredi. Trois
marqueurs `ATELIER 2` y indiquent ce qu'il faut ajouter.

---

## Étape 1 — Les trois primitives (5 min)

Prometheus n'a besoin que de trois types de métriques :

| Primitive | Pour quoi | Exemple ici |
|---|---|---|
| `Counter` | ce qui ne fait que monter | nombre de prédictions |
| `Histogram` | une distribution de valeurs | latence d'inférence |
| `Gauge` | une valeur qui monte et descend | score moyen glissant |

Vérifiez que chaque métrique porte le label `version_modele`.

> **Pourquoi ce label est non négociable.** Sans lui, vous ne pouvez ni comparer
> un champion et un challenger, ni imputer une dégradation à un déploiement
> précis. C'est l'erreur la plus coûteuse et la moins visible du monitoring ML.

Vérifiez ensuite que la réponse de `/predict` contient bien `version_modele` :

```bash
make serve   # dans un terminal
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"montant":45000,"heure":21,"frequence_7j":4,"anciennete_jours":35,"type_contrepartie":"particulier"}'
```

Puis regardez la sortie brute des métriques : <http://localhost:8000/metrics>

---

## Étape 2 — Lancer la pile (4 min)

```bash
make up      # pile Docker : API sur le port 8001
```

Trois conteneurs démarrent :

| Service | Adresse | Rôle |
|---|---|---|
| API | <http://localhost:8001/docs> | le service de prédiction |
| Prometheus | <http://localhost:9091> | collecte les métriques toutes les 5 s |
| Grafana | <http://localhost:3002> | les affiche |

Le tableau de bord est **pré-provisionné** : vous n'avez rien à construire. Il
s'appelle « TAISS 2026 — Détection de fraude », dans le dossier TAISS 2026.

---

## Étape 3 — Générer du trafic (4 min)

```bash
make replay
```

Cinq cents requêtes de trafic normal. Retournez sur Grafana et regardez les
courbes se remplir. Notez le **taux de signalement** : il tourne autour de 1 %,
ce qui est cohérent avec la prévalence de la fraude en 2025.

Retenez ce chiffre. Il va servir à l'atelier 3.

---

## Étape 4 — Reconstruire avec le tag du commit (2 min)

```bash
docker build -t fraude:$(git rev-parse --short HEAD) .
docker images | grep fraude
```

Une image taguée avec le hash du commit est une image dont on sait exactement
d'où elle vient — et vers laquelle on peut revenir en une commande.

---

## Critères de réussite

- [ ] `/metrics` répond et affiche les compteurs
- [ ] Le tableau de bord Grafana montre le trafic en temps réel
- [ ] La version du modèle apparaît dans la réponse de l'API **et** dans les labels
- [ ] Une image taguée avec le hash du commit existe localement

---

## Ce qui bloque habituellement

| Symptôme | Que faire |
|---|---|
| `port is already allocated` | Des conteneurs tournent encore : `docker compose down`, puis `docker ps -a` |
| Le tableau de bord reste vide | Aucun trafic généré, ou la cible Prometheus est fausse. Vérifiez <http://localhost:9091/targets> : la cible `api:8000` doit être `UP` |
| Mémoire insuffisante | Trois conteneurs sur une machine modeste. Binômez sur le poste le plus puissant |
| Grafana demande un mot de passe | L'accès anonyme est activé dans `docker-compose.yml` ; sinon `admin` / `admin` |

---

## La question à se poser

Votre tableau de bord montre la latence, le débit et le taux de signalement.
Aucune de ces courbes ne dit si le modèle a raison. Pourquoi ? Et que faudrait-il
pour le savoir ?
