# Agent skills

## Agent skills

### Issue tracker

Issues are tracked as GitHub issues on `ShmuelAmir/chess-openings` (use the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Uses standard triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`. The glossary holds domain language only. Layers, seams, caching and data flows live in `docs/architecture.md`.

### Checking UI changes

Whenever you change the frontend, run `make dev-sample` (or `cd frontend && npm run dev:sample`) and open http://localhost:5174 to see the change on the real Recall page with sample data, no Lichess sign-in or backend needed, and take a screenshot before you finish.

### Shell commands in a worktree

Work here usually runs in a git worktree, where a guard refuses any shell call it can't confirm stays inside it. Make each shell call one plain command, run from the worktree root with absolute paths. Create and change files with your file-editing tools; put a multi-line script in a file under your scratch directory and run that file. End each call on the command whose exit status you care about, so a closing `ls` or `grep` that finds nothing doesn't mark a good call failed.
