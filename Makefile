# Commandes unifiées : la CI exécute exactement les mêmes cibles que le développeur.
.DEFAULT_GOAL := help
API := services/api
WEB := frontend
DATA := data
INTERNS ?= 200

.PHONY: help install lint format typecheck test test-unit test-integration test-data test-web openapi check up down logs migrate migration create-hr seed pipeline clean

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Installe les dépendances et les hooks Git
	uv sync --all-packages
	cd $(WEB) && npm ci
	uv run pre-commit install --hook-type pre-commit --hook-type commit-msg

lint: ## Analyse statique (Ruff)
	uv run ruff check .
	uv run ruff format --check .

format: ## Formate et corrige automatiquement
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## Vérification des types (mypy strict)
	cd $(API) && uv run mypy
	cd $(DATA) && uv run mypy

test-unit: ## Tests rapides (sans base de données)
	cd $(API) && uv run pytest -m "not integration" --no-cov

test-integration: ## Tests d'intégration (PostgreSQL via Docker)
	cd $(API) && uv run pytest -m integration --no-cov

test: ## Toute la suite de tests avec couverture
	cd $(API) && uv run pytest

test-data: ## Tests du pipeline PySpark (Java 17+ requis, sinon passer par Docker)
	cd $(DATA) && uv run pytest

test-web: ## Lint, typage et tests du frontend React
	cd $(WEB) && npm run lint && npm run typecheck && npm test

openapi: ## Régénère le contrat OpenAPI et les types TypeScript du frontend
	cd $(API) && uv run python -m internflow_api.cli export-openapi --output openapi.json
	cd $(WEB) && npm run gen:api

check: lint typecheck test test-data test-web ## Tout ce que la CI vérifie

up: ## Démarre l'environnement local (PostgreSQL + migrations + API)
	docker compose up --build -d
	@echo "Application : http://localhost:$${WEB_PORT:-8080}"
	@echo "API : http://localhost:$${API_PORT:-8000}/docs"

down: ## Arrête l'environnement local
	docker compose down

logs: ## Suit les logs de l'API
	docker compose logs -f api

migrate: ## Applique les migrations sur la base locale
	cd $(API) && uv run alembic upgrade head

migration: ## Crée une migration : make migration m="description"
	cd $(API) && uv run alembic revision --autogenerate -m "$(m)"

create-hr: ## Crée un compte RH : make create-hr email=rh@exemple.ma
	docker compose run --rm migrate python -m internflow_api.cli create-hr-user --email "$(email)"

seed: ## Génère des données fictives : make seed INTERNS=200
	docker compose run --rm data seed --interns $(INTERNS)

pipeline: ## Exécute le pipeline bronze → silver → gold
	docker compose run --rm data pipeline

clean: ## Supprime les caches
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache -o -name htmlcov \) -prune -exec rm -rf {} +
