# Issue tracker: GitHub Issues

Issues and PRDs for this repo live as GitHub issues on `ShmuelAmir/chess-openings`. Use the `gh` CLI for all operations.

## Conventions

- One issue per PRD or implementation task
- A PRD is an issue whose title starts with `PRD:`; its implementation issues link back to it with `Part of #<PRD number>` in the body
- Wayfinder map tickets carry a `wayfinder:<kind>` label (`map`, `grilling`, `research`, `prototype`, `task`) and are closed when resolved
- Triage state is recorded as a label (see `triage-labels.md` for the label strings)
- Conversation history lives in issue comments

## When a skill says "publish to the issue tracker"

Create an issue with `gh issue create --title "<title>" --body-file <file> --label <label>`.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`. The user will normally pass the issue number or URL directly.
