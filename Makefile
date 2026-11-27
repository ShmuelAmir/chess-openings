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

# The frontend on sample data, no Lichess sign-in or backend (port 5174)
dev-sample:
	cd frontend && npm run dev:sample

build:
	cd frontend && npm run build

test-frontend:
	cd frontend && npm test

# Install all dependencies
install-all: install
	cd frontend && npm install

.PHONY: run install test test-backend test-frontend dev dev-sample build install-all
