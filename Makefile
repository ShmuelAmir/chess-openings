# Chess Opening Analyzer - Makefile

# Backend commands
run:
	cd backend && source venv/bin/activate && uvicorn main:app --reload

install:
	cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Frontend commands
dev:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

# Install all dependencies
install-all: install
	cd frontend && npm install

.PHONY: run install dev build install-all
