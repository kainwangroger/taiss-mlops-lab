# Mise en ligne du dépôt du lab

**TAISS 2026 · Filière F3 · Lab MLOps CI/CD et monitoring**

Deux fichiers vous sont livrés :

| Fichier | Ce que c'est |
|---|---|
| `taiss-mlops-lab.zip` | le dépôt complet, historique Git inclus |
| `taiss-mlops-lab.bundle` | le même dépôt sous forme de bundle Git, plus léger |

---

## Depot GitHub du lab

Le depot de travail est deja disponible ici :

https://github.com/kainwangroger/taiss-mlops-lab

Pour recuperer le lab :

```powershell
git clone https://github.com/kainwangroger/taiss-mlops-lab.git
cd taiss-mlops-lab
```

Sous Linux :

```bash
git clone https://github.com/kainwangroger/taiss-mlops-lab.git
cd taiss-mlops-lab
```

Le depot est deja publie. Les commandes ci-dessous servent uniquement a
comprendre la procedure de publication d'un nouveau depot.

## Travailler pendant le TP

Commencez depuis `main`, qui est la version de depart des participants :

```bash
git switch main
git pull origin main
```

Pour travailler dans une branche personnelle :

```bash
git switch -c prenom-atelier-1
```

Apres une modification :

```bash
git add .
git commit -m "Completer le contrat de donnees"
git push -u origin prenom-atelier-1
```

Ouvrez ensuite une Pull Request vers `main` pour declencher GitHub Actions.
Les Actions doivent etre activees dans l'onglet **Actions** du depot, en
particulier sur un fork.

## Les branches du depot

Les corriges sont conserves dans des branches separees et ne doivent pas etre
utilises par les participants avant la correction collective :

```bash
git branch -r
```

Branches disponibles :

| Branche | Utilisation |
|---|---|
| `main` | version de depart a utiliser pendant le TP |
| `solution-atelier-1` | corrige du contrat de donnees |
| `solution-atelier-2` | corrige de l'instrumentation de l'API |
| `solution-atelier-3` | corrige final et analyse de derive |

Les branches `solution-*` sont des supports pour l'animateur. Elles existent
sur GitHub pour permettre une verification ou rattraper un participant, mais
le groupe travaille sur `main` ou sur une branche personnelle.

> Variante avec le bundle : `git clone taiss-mlops-lab.bundle taiss-mlops-lab`
> puis remplacez le remote `origin` par l'adresse GitHub.

Chaque branche de solution contient la precedente : `solution-atelier-3` est
l'etat final complet.

---

## À faire avant jeudi

### 1. Activer les Actions et vérifier la CI

Poussez `main`, ouvrez une pull request de test, et vérifiez que le workflow
part. **Faites le test depuis un compte tiers** — un fork se comporte
différemment du dépôt d'origine, et c'est là que ça casse habituellement.

### 2. Intégrer le travail de mercredi

Deux emplacements sont marqués `NOTE POUR LES ENCADRANTS` :

- `Dockerfile`
- `src/serve.py`

Remplacez-les par ceux produits lors de la séance « Exposer un modèle en API ».
Le lab n'exige que trois choses du service : une route `POST /predict`, le champ
`version_modele` dans la réponse, et une route `GET /metrics`.

C'est le point d'ancrage principal de la séance. Si les participants ne
reconnaissent pas leur propre travail dans le dépôt, le lab devient hors sol.

### 3. Convenir du nommage des images avec le bloc B

L'image publiée à l'atelier 2 est taguée avec le hash court du commit :
`fraude:<sha7>`. Calez cette convention avec l'animateur de la session
Kubernetes pour qu'il déploie exactement cette image à 15:15.

### 4. Préparer l'image de base hors ligne

```bash
docker build -t fraude:base .
docker save fraude:base | gzip > fraude-base.tar.gz
```

Copiez le fichier sur deux clés USB. Trente `pip install` et `docker pull`
simultanés sur la connexion de la salle, c'est le scénario qui tue les ateliers.

### 5. Rejouer les trois ateliers sur une machine vierge

Chronomètre en main, en conditions réelles. C'est la seule façon de valider les
minutages du guide d'animation.

---

## Une retouche à faire dans le support de présentation

**Slide 26, ligne « 2. Produire le rapport ».** Elle indique aujourd'hui
« Evidently : DataDriftPreset, puis save_html ». Remplacez par :

```
python -m src.drift_report
```

Le rapport de dérive du dépôt calcule PSI, Kolmogorov–Smirnov et khi-deux avec
numpy et scipy, et produit un HTML autoportant. Ce choix est délibéré : l'API
d'Evidently change entre versions majeures, et un atelier de dix minutes ne peut
pas dépendre de cela. Evidently reste cité dans les ressources, slide 33.

---

## Ce que le lab doit produire, chiffré

Ces valeurs sont vérifiées sur ce dépôt. Si vous obtenez autre chose après avoir
intégré le service de mercredi, quelque chose a bougé.

**Modèle entraîné**

| Métrique | Valeur | Seuil |
|---|---|---|
| F1 | 0,73 | 0,60 |
| Rappel | 0,80 | 0,45 |
| ROC AUC | 0,996 | — |

**Atelier 1** — à `seuil_f1: 0.95`, la CI échoue avec :
`seuil de qualité non tenu : F1 = 0.7273, seuil exigé = 0.9500`

**Atelier 2** — taux de signalement sur le trafic 2025 : environ 1 %

**Atelier 3** — taux de signalement sur le trafic 2026 : environ 15 %

**Rapport de dérive**

```
type_contrepartie    5.666   DÉRIVE AVÉRÉE  ← nouvelle catégorie : marchand
montant              0.470   DÉRIVE AVÉRÉE
heure                0.450   DÉRIVE AVÉRÉE
frequence_7j         0.443   DÉRIVE AVÉRÉE
anciennete_jours     0.055   STABLE
```

**Analyse segmentée** — le chiffre qui règle le débat de la restitution :

| Segment | Signalement |
|---|---|
| marchand | 34,0 % |
| particulier | 0,8 % |
| agent | 3,8 % |
| facture | 0,0 % |

Le segment particulier est resté exactement à son niveau de 2025. Le modèle
n'est pas cassé : la dérive est entièrement localisée sur une population qui
n'existait pas. C'est ce tableau qui démontre que « réentraîner globalement »
est la mauvaise réponse.

---

## Le message à envoyer aux participants

Il est prêt en annexe A du guide d'animation. Envoyez-le mercredi soir, avec
l'URL du dépôt, et insistez sur un point : **activer les Actions sur le fork.**
GitHub les désactive par défaut, et c'est le blocage numéro un de l'atelier 1.
