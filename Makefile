# Convenience targets (Unix/macOS, or Windows with `make`).
# Windows users without make: use scripts\dev.ps1 instead.

PY ?= python3
VENV = backend/.venv
VPY = $(VENV)/bin/python

.PHONY: install migrate dev test e2e eval up down fmt

install:
	$(PY) -m venv $(VENV)
	$(VPY) -m pip install --upgrade pip
	$(VPY) -m pip install -e "./backend[dev]"
	cd frontend && npm install || true

migrate:
	cd backend && ../$(VENV)/bin/alembic upgrade head

dev:
	bash scripts/dev.sh

test:
	cd backend && ../$(VENV)/bin/python -m pytest tests -v

e2e:
	cd frontend && npx playwright test

eval:
	cd backend && ../$(VENV)/bin/python -m app.eval.cli run --golden golden

up:
	docker compose up --build

down:
	docker compose down

fmt:
	$(VPY) -m ruff format backend/app
	$(VPY) -m ruff check --fix backend/app
