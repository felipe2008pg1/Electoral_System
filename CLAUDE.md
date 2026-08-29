# CLAUDE.md

Context file for AI agents working on this repository. Read this before making any change.

## Project Purpose

A web-based mock electoral/voting system built for academic/educational purposes (studying Flask backend architecture). Fictional candidates only — no real political affiliation. Not a production voting system and never should be treated as one (no legal/compliance requirements around real elections apply, but standard web security practices still do).

## Current Stack

- **Backend:** Python 3.x, Flask
- **Persistence:** local JSON file (`votes.json`), no database
- **Frontend:** server-rendered Jinja2 templates, plain HTML5/CSS3 (no JS framework, no build step)
- **Tests:** none yet (see TODO.md)

## Development Rules

1. `app.py` is the single source of truth for the running application. The `scripts/` directory contains a legacy/unfinished CLI prototype that is **not wired into the web app** — do not assume code there is used or correct.
2. Keep one data schema. Candidate records use `{"candidate": str, "votes": int}` (English keys, matches `app.py`). Do not reintroduce the old `candidato`/`votos` Portuguese schema.
3. Do not add a database or frontend framework unless explicitly requested — the JSON-file + server-rendered-HTML architecture is intentional for this project's scope.
4. Every state-changing route (`POST`/`PUT`/`DELETE`) must be CSRF-protected.
5. Every write to `votes.json` must go through a single locked read-modify-write helper to avoid race conditions — never open/write the file ad hoc from route handlers.
6. Never run with `debug=True` outside local development. Debug mode must be controlled by an environment variable, defaulting to `False`.
7. All user-supplied input (form fields, query params) must be validated against an explicit allow-list (e.g. candidate must exist in the current candidate list) before use.
8. No secrets, tokens, or environment-specific config hardcoded in source. Use environment variables (`.env` for local dev, never committed).
9. Do not delete `scripts/` without explicit confirmation from the project owner, even though it is currently dead code — flag it in TODO.md instead.

## Security Requirements (baseline for this project)

- CSRF protection on all forms (Flask-WTF or equivalent).
- Security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy`, `Referrer-Policy`.
- Rate limiting on `/vote` (per-IP) to reduce trivial vote-spam abuse.
- No stack traces or internal errors shown to the client in production (custom error handlers).
- Input validation on every form field; never trust `request.form`/`request.args` directly.
- File writes to `votes.json` must be atomic and lock-protected.

## Coding Conventions

- PEP 8, type hints on new/modified functions.
- Keep route handlers thin — business logic (vote validation, persistence) lives in helper modules, not inline in `app.py`.
- Prefer explicit error handling over silent `except: pass`.
- English for all new code, comments, and commit messages (matches the translated README).

## Before Modifying This Project

- Check `ARCHITECTURE.md` for current structure before adding files.
- Check `TODO.md` for known issues before "discovering" them again.
- Check `DECISIONS.md` before re-litigating a settled architectural choice.
- Update `CHANGELOG_AI.md` after any meaningful change.