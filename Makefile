# Chess Opening Analyzer - Makefile

# Backend commands
run:
	cd backend && source venv/bin/activate && uvicorn main:app --reload

install:
	cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements-dev.txt

test-backend:
	cd backend && venv/bin/pytest

# Backend and frontend suites
test: test-backend test-frontend

# Frontend commands
dev:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

test-frontend:
	cd frontend && npm test

# Lint and format (ruff for the backend, Prettier for the frontend).
# `lint` only checks; `format` rewrites files.
lint: lint-backend lint-frontend

lint-backend:
	cd backend && venv/bin/ruff check . && venv/bin/ruff format --check .

lint-frontend:
	cd frontend && npm run lint

format: format-backend format-frontend

format-backend:
	cd backend && venv/bin/ruff check --fix . && venv/bin/ruff format .

format-frontend:
	cd frontend && npm run format

# Install all dependencies
install-all: install
	cd frontend && npm install

.PHONY: run install test test-backend test-frontend dev build install-all \
	lint lint-backend lint-frontend format format-backend format-frontend
