# ARCHITECTURE.md

Documents what actually exists in the repository today. Updated when the architecture changes.

## Project Structure

```
Electoral_System_V.1.0/
├── app.py                 # Flask entrypoint: routes, in-app data load/save
├── scripts/                # Legacy CLI prototype — NOT used by app.py (see note below)
│   ├── data.py             # Hardcoded candidate seed list (own schema)
│   ├── system.py           # Terminal-based voting loop
│   └── tools.py            # Helpers for the CLI prototype (currently corrupted file)
├── static/
│   └── style.css           # Dark-mode UI styling
├── templates/
│   └── index.html          # Ballot UI (currently mismatched with app.py — see TODO.md)
├── votes.json               # Runtime data file, created on first run (not committed)
└── README.md
```

> **Note on `scripts/`:** This is an earlier, unfinished terminal-based version of the app. It is never imported by `app.py` and is not part of the running web application. Treat it as reference/legacy only until a decision is made to remove or revive it (see DECISIONS.md).

## Backend Architecture

Single-file Flask app (`app.py`):

- `load_data()` — reads `votes.json`; creates it with default seed data (`FELIPE`, `GONZALEZ`) if missing.
- `save_data(data)` — overwrites `votes.json` with the full candidate list.
- `GET /` — loads candidates, renders `templates/index.html`.
- `POST /vote` — reads `candidate` from form body, increments matching candidate's vote count, saves, redirects to `/`.

No blueprints, no service layer, no database layer — everything lives in route handlers.

## Data Model

`votes.json` — a flat JSON array:

```json
[
  {"candidate": "FELIPE", "votes": 0},
  {"candidate": "GONZALEZ", "votes": 0}
]
```

This is the only schema the running app uses. (`scripts/data.py` defines a different, unused schema — `candidato`/`votos` — do not treat it as authoritative.)

## Frontend Architecture

- Server-rendered Jinja2 template (`templates/index.html`), one `<form>` per candidate posting to a vote endpoint.
- Single stylesheet (`static/style.css`), no JS.
- **Known break:** the template currently references `candidatos` (list var name) and `c.candidato` / `c.votos` (field names) and posts to `/votar`, none of which match `app.py`'s `candidates`, `c.candidate` / `c.votes`, and `/vote`. This must be fixed before anything else — the app does not currently function end-to-end.

## Authentication / Authorization

None. There is no login, no session, no admin area. Any visitor can vote any number of times. This is acceptable for the project's stated academic scope but should be called out to anyone extending it toward "real" election semantics (see README's stated future direction).

## APIs

No JSON/REST API — purely server-rendered HTML + form posts.

## Important Dependencies

- `Flask` (only third-party dependency). No `requirements.txt` currently committed (see TODO.md).

## Data Flow

1. Browser requests `GET /` → Flask loads `votes.json` → renders template with current vote counts.
2. User submits vote form → `POST /vote` with `candidate` in form body → Flask loads `votes.json`, increments count for matching candidate, writes file, redirects to `GET /`.

No caching, no queueing, no locking — each request performs a full file read/write.