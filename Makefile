.PHONY: help smoke install install-console train evaluate test lint serve console replay drift up down logs clean

help:
	@echo "Cibles disponibles :"
	@echo "  make install    installe les dépendances"
	@echo "  make smoke      vérifie que le poste est prêt   <- à lancer en premier"
	@echo "  make train      entraîne le modèle"
	@echo "  make test       lance toute la suite de tests"
	@echo "  make lint       vérifie le style"
	@echo "  make serve      démarre l'API en local sur le port 8000"
	@echo "  make console    ouvre la console du participant sur le port 8501"
	@echo "  make up         démarre l'API + Prometheus + Grafana (atelier 2)"
	@echo "  make replay     rejoue du trafic normal"
	@echo "  make drift      rejoue le trafic 2026 et produit le rapport (atelier 3)"
	@echo "  make logs       affiche la fin du journal logs/lab.log"
	@echo "  make down       arrête la pile"

install:
	pip install -r requirements.txt

install-console:
	pip install -r requirements-console.txt

smoke:
	@echo "1/4  version de Python"
	@python -c "import sys; v=sys.version_info; assert v[:2]>=(3,11), 'Python 3.11 requis'; print('     ', sys.version.split()[0])"
	@echo "2/4  dépendances"
	@python -c "import pandas, sklearn, fastapi, prometheus_client, yaml; print('      OK')"
	@echo "3/4  jeux de données"
	@python -c "import pandas as pd; d=pd.read_csv('data/reference_2025.csv'); print(f'      reference_2025.csv : {len(d)} lignes')"
	@echo "4/4  entraînement rapide"
	@python -m src.train > /dev/null && echo "      modèle entraîné"
	@echo ""
	@echo "OK — votre poste est prêt."

train:
	python -m src.train

evaluate:
	python -m src.evaluate

test:
	pytest tests/ -q

lint:
	ruff check src tests

serve:
	uvicorn src.serve:app --host 0.0.0.0 --port 8000 --reload

# La console lancée ici voit votre environnement Python réel : elle peut donc
# valider l'onglet « Mon poste » en entier, ce que la version Docker ne peut pas.
console:
	streamlit run src/console.py --server.port 8501 --browser.gatherUsageStats false

replay:
	python -m src.replay --n 500 --url http://localhost:8001

drift:
	python -m src.replay --input data/drifted_2026.csv --n 800 --url http://localhost:8001
	python -m src.drift_report
	@echo ""
	@echo "Ouvrez reports/derive.html dans votre navigateur."

up:
	docker compose up -d --build
	@echo ""
	@echo "  Console    http://localhost:8502     <- commencez ici"
	@echo "  API        http://localhost:8001/docs"
	@echo "  Prometheus http://localhost:9091"
	@echo "  Grafana    http://localhost:3002"

# Tout ce que produisent l'entraînement, la porte de qualité, le rejeu, le
# rapport et le service converge dans ce seul fichier.
logs:
	@tail -n 40 logs/lab.log 2>/dev/null || echo "Aucun journal pour l'instant. Lancez make train."

down:
	docker compose down

clean:
	rm -rf models/*.pkl reports/*.json reports/*.html reports/*.csv logs/*.log logs/*.log.*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
