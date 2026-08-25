.PHONY: help smoke install train evaluate test lint serve replay drift up down clean

help:
	@echo "Cibles disponibles :"
	@echo "  make install    installe les dépendances"
	@echo "  make smoke      vérifie que le poste est prêt   <- à lancer en premier"
	@echo "  make train      entraîne le modèle"
	@echo "  make test       lance toute la suite de tests"
	@echo "  make lint       vérifie le style"
	@echo "  make serve      démarre l'API en local sur le port 8000"
	@echo "  make up         démarre l'API + Prometheus + Grafana (atelier 2)"
	@echo "  make replay     rejoue du trafic normal"
	@echo "  make drift      rejoue le trafic 2026 et produit le rapport (atelier 3)"
	@echo "  make down       arrête la pile"

install:
	pip install -r requirements.txt

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
	@echo "  API        http://localhost:8001/docs"
	@echo "  Prometheus http://localhost:9091"
	@echo "  Grafana    http://localhost:3002"

down:
	docker compose down

clean:
	rm -rf models/*.pkl reports/*.json reports/*.html reports/*.csv
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
