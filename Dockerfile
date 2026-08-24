# ------------------------------------------------------------------------------
# NOTE POUR LES ENCADRANTS
# Ce Dockerfile est l'emplacement prévu pour celui produit par les participants
# lors de la séance « Conteneurisation avec Docker » du mercredi. Si vous
# disposez du leur, remplacez-le ici : le lab ne dépend que du fait que
# l'image expose le service sur le port 8000.
# ------------------------------------------------------------------------------

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Les dépendances d'abord : cette couche est mise en cache tant que
# requirements.txt ne change pas. C'est ce qui rend les reconstructions rapides.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY params.yaml .
COPY src/ ./src/
COPY data/ ./data/

# Le modèle est entraîné au moment du build : l'image est autoportante et
# reproductible. En production réelle, on récupérerait plutôt un artefact
# depuis un registre de modèles.
RUN python -m src.train

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uvicorn", "src.serve:app", "--host", "0.0.0.0", "--port", "8000"]
