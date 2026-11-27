# Chess Opening Analyzer - Makefile

# A git worktree has no venv or node_modules of its own, so the test targets
# fall back to the main checkout's copies. The test code still comes from here.
MAIN_ROOT := $(shell dirname "$$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || echo .git)")
find-dep = $(firstword $(wildcard $(CURDIR)/$1 $(MAIN_ROOT)/$1))
PYTEST := $(call find-dep,backend/venv/bin/pytest)
# Vitest leaves a cache in frontend/node_modules/.vite, so look for an installed
# binary rather than the folder.
VITEST := $(call find-dep,frontend/node_modules/.bin/vitest)
NODE_MODULES := $(VITEST:%/.bin/vitest=%)

# Backend commands
run:
	cd backend && source venv/bin/activate && uvicorn main:app --reload

install:
	cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements-dev.txt

test-backend:
	@test -n "$(PYTEST)" || { echo "No Python venv in backend/ here or in the main checkout ($(MAIN_ROOT)). Run 'make install-all'." >&2; exit 1; }
	cd backend && $(PYTEST)

# Backend and frontend suites
test: test-backend test-frontend

# Frontend commands
dev:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

# Outside the main checkout, link ./node_modules to the main checkout's copy:
# Node finds it by walking up from frontend/, and a later `npm install` in
# frontend/ makes its own folder instead of writing through the link.
test-frontend:
	@test -n "$(NODE_MODULES)" || { echo "No node_modules in frontend/ here or in the main checkout ($(MAIN_ROOT)). Run 'make install-all'." >&2; exit 1; }
	@if [ "$(NODE_MODULES)" != "$(CURDIR)/frontend/node_modules" ] && { [ -L node_modules ] || [ ! -e node_modules ]; }; then ln -sfn "$(NODE_MODULES)" node_modules; fi
	cd frontend && npm test

# Install all dependencies
install-all: install
	cd frontend && npm install

.PHONY: run install test test-backend test-frontend dev build install-all
