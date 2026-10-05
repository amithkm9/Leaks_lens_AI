.PHONY: setup user dev test build evaluate e2e compose-up compose-user purge recover migrate
setup:
	python3 scripts/setup.py
	uv sync --project backend --python 3.12 --frozen
	cd frontend && npm ci
	cd backend && .venv/bin/alembic upgrade head
user:
	cd backend && .venv/bin/python -m app.cli create-user
migrate:
	cd backend && .venv/bin/alembic upgrade head
dev:
	python3 scripts/dev.py
test:
	cd backend && PATH="$(CURDIR)/.data/bin:$$PATH" .venv/bin/pytest -q
build:
	cd frontend && npm run build
evaluate:
	cd backend && PATH="$(CURDIR)/.data/bin:$$PATH" .venv/bin/python -m app.evaluation --split development
e2e:
	cd frontend && npm run test:e2e
compose-up:
	docker compose up --build -d
compose-user:
	docker compose exec api python -m app.cli create-user
purge:
	cd backend && .venv/bin/python -m app.cli purge-raw
recover:
	cd backend && .venv/bin/python -m app.cli recover-jobs
detectors:
	python3 scripts/install_gitleaks.py
compose-test:
	docker compose exec -T api python < scripts/compose_smoke.py
