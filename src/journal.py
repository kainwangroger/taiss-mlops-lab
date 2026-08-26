"""
Journal du lab.

Tout ce que produisent l'entraînement, la porte de qualité, le rejeu de trafic,
le rapport de dérive et le service atterrit dans un seul fichier :

    logs/lab.log

La sortie du terminal ne change pas — `dire()` affiche **et** journalise. C'est
volontaire : les documents des ateliers citent les sorties attendues, et un
participant qui ne voit plus ce qu'il attendait croit que quelque chose a cassé.

Le fichier est en revanche la seule trace qui survit à la fermeture du terminal.
C'est celle qu'on lit quand un participant dit « ça ne marche pas » sans pouvoir
dire ce qu'il a lancé.

Usage :
    from src import journal
    log = journal.configurer("train")
    journal.dire(log, "Modèle entraîné")
"""

import logging
import logging.handlers
import pathlib
import time

RACINE = pathlib.Path(__file__).resolve().parents[1]
DOSSIER = RACINE / "logs"
FICHIER = DOSSIER / "lab.log"

FORMAT = "%(asctime)s | %(name)-9s | %(levelname)-7s | %(message)s"
HORODATAGE = "%Y-%m-%d %H:%M:%S"

# 2 Mo par fichier, deux archives : un lab entier tient largement dedans, et une
# boucle de rejeu emballée ne peut pas remplir le disque du participant.
TAILLE_MAX = 2_000_000
ARCHIVES = 2


def configurer(nom: str) -> logging.Logger:
    """Renvoie le logger de `nom`, écrivant dans logs/lab.log."""
    logger = logging.getLogger(nom)
    if logger.handlers:
        return logger

    DOSSIER.mkdir(exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        FICHIER, maxBytes=TAILLE_MAX, backupCount=ARCHIVES, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(FORMAT, datefmt=HORODATAGE))

    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    # Sans cela, la configuration racine de uvicorn dupliquerait chaque ligne.
    logger.propagate = False
    return logger


def dire(logger: logging.Logger, message: str = "") -> None:
    """Affiche sur la sortie standard **et** journalise."""
    print(message)
    if message.strip():
        logger.info(message.strip())


def demarrer(logger: logging.Logger, quoi: str, **contexte) -> None:
    """Ouvre une entrée de journal repérable, avec son contexte."""
    details = " ".join(f"{cle}={valeur}" for cle, valeur in contexte.items())
    logger.info(f"--- début : {quoi} {details}".rstrip())


def observer_requetes(app, logger: logging.Logger):
    """
    Journalise chaque requête HTTP du service.

    `/metrics` est exclu : Prometheus l'interroge toutes les cinq secondes et
    noierait tout le reste.
    """

    @app.middleware("http")
    async def _journaliser(request, call_next):
        debut = time.perf_counter()
        reponse = await call_next(request)
        duree = (time.perf_counter() - debut) * 1000
        if request.url.path != "/metrics":
            logger.info(
                f"{request.method} {request.url.path} "
                f"-> {reponse.status_code} en {duree:.1f} ms"
            )
        return reponse

    return app
