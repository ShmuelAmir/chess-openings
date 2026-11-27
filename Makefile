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
# `.` rather than `source`: make runs recipes in /bin/sh, which is dash on
# Ubuntu (and the CI runner) and has no `source`.
run:
	cd backend && . venv/bin/activate && uvicorn main:app --reload

install:
	cd backend && python3 -m venv venv && . venv/bin/activate && pip install -r requirements-dev.txt

test-backend:
	@test -n "$(PYTEST)" || { echo "No Python venv in backend/ here or in the main checkout ($(MAIN_ROOT)). Run 'make install-all'." >&2; exit 1; }
	cd backend && $(PYTEST)

# Backend, frontend and repo-script suites
test: test-backend test-frontend test-scripts

test-scripts:
	@test -n "$(PYTEST)" || { echo "No Python venv in backend/ here or in the main checkout ($(MAIN_ROOT)). Run 'make install-all'." >&2; exit 1; }
	$(PYTEST) -q scripts

# Frontend commands
dev:
	cd frontend && npm run dev

# The frontend on sample data, no Lichess sign-in or backend (port 5174)
dev-sample:
	cd frontend && npm run dev:sample

build:
	cd frontend && npm run build

# Outside the main checkout, link ./node_modules to the main checkout's copy:
# Node finds it by walking up from frontend/, and a later `npm install` in
# frontend/ makes its own folder instead of writing through the link.
define link-node-modules
	@test -n "$(NODE_MODULES)" || { echo "No node_modules in frontend/ here or in the main checkout ($(MAIN_ROOT)). Run 'make install-all'." >&2; exit 1; }
	@if [ "$(NODE_MODULES)" != "$(CURDIR)/frontend/node_modules" ] && { [ -L node_modules ] || [ ! -e node_modules ]; }; then ln -sfn "$(NODE_MODULES)" node_modules; fi
endef

test-frontend:
	$(link-node-modules)
	cd frontend && npm test

# Lint and format (ruff for the backend, Prettier and tsc for the frontend, and a check
# that every Markdown doc named in code or docs exists).
# `lint` only checks; `format` rewrites files. Both report every half and every
# check before failing, so one problem doesn't hide another.
lint:
	@$(MAKE) -k lint-backend lint-frontend lint-docs

lint-backend:
	cd backend && venv/bin/ruff check .; s=$$?; venv/bin/ruff format --check . && exit $$s

# Prettier, the TypeScript type check, then a check that src/ holds no JavaScript;
# fails if any does. tsc skips .js files, so without the last check a stray one
# would pass unchecked (docs/adr/0002-frontend-typescript.md).
lint-frontend:
	$(link-node-modules)
	cd frontend && npm run lint; s=$$?; npm run typecheck || s=1; \
	js=$$(find src -name '*.js' -o -name '*.jsx'); \
	if [ -n "$$js" ]; then echo "JavaScript in frontend/src; the frontend is TypeScript only:" >&2; echo "$$js" >&2; s=1; fi; \
	exit $$s

lint-docs:
	python3 scripts/check_md_links.py

format:
	@$(MAKE) -k format-backend format-frontend

# --exit-zero: errors ruff can't fix are reported but don't stop the formatter.
format-backend:
	cd backend && venv/bin/ruff check --fix --exit-zero . && venv/bin/ruff format .

format-frontend:
	cd frontend && npm run format

# Install all dependencies
install-all: install
	cd frontend && npm install

.PHONY: run install test test-backend test-frontend test-scripts dev dev-sample build install-all \
	lint lint-backend lint-frontend lint-docs format format-backend format-frontend
