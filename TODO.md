# TODO.md

Prioritized roadmap. Update when items are completed or new important ones are found.

## Critical — V1 (Flask, legacy, on hold pending owner decision — see DECISIONS.md #5)

- [ ] Fix `templates/index.html` vs `app.py` mismatch (`candidatos`→`candidates`, `candidato`/`votos`→`candidate`/`votes`, `/votar`→`/vote`). App does not work end-to-end right now.
- [ ] Fix corrupted `scripts/tools.py` (wrapped in literal markdown code fence) — or remove `scripts/` entirely once a decision is made (see DECISIONS.md).
- [ ] Add file locking / atomic write for `votes.json` to prevent lost updates under concurrent requests (race condition).
- [ ] Disable `debug=True` by default; control via `FLASK_DEBUG` env var, default off.

## Critical — V2 (FastAPI/Redis/PostgreSQL, active development)

- [x] Phase 1: Docker Compose skeleton, FastAPI health check, DB schema.
- [x] Phase 2: CPF validation, `POST /vote`, Redis Stream queue push, per-IP rate limiting.
- [x] Phase 3: Background worker consuming `votes:pending` via `XREADGROUP` — ACID transaction (insert `voters_registry`, increment `candidates.votes_count`, append `audit_chain` block), with retry/ack and dead-letter handling for poison messages.
- [ ] Phase 4: WebSocket server broadcasting live results on `audit_chain` commit.
- [ ] Session-based rate limiting (spec requires it; only per-IP exists today) — needs a session/device-identity scheme first (signed cookie or similar).
- [ ] Periodic (not just startup) reclaim of stale pending Redis Stream messages — currently `reclaim_stale()` only runs once when the worker boots, so a message stuck mid-processing while the worker stays alive but hangs won't be retried until a restart.
- [ ] Chain verification endpoint/script: walk `audit_chain` ordered by `seq`, recompute each `entry_hash` from its own fields, confirm it matches the stored value and the next row's `previous_hash`.
- [ ] Admin write path for `candidates` table — currently no way to create/seed candidates except direct SQL.
- [ ] Replace hardcoded `app_worker` bootstrap password in `infra/postgres/init.sql` with an `ALTER ROLE` step driven by an env var during deploy.
- [ ] Resolve/accept the CPF hashing entropy problem before calling this system "anonymous" (see DECISIONS.md #5).
- [ ] Randomized/batched delay between vote acceptance and audit-chain commit to reduce voter/vote timing correlation.
- [ ] Admin authentication/authorization for candidate CRUD and WebSocket result stream access.

## High Priority

- [ ] Add CSRF protection to the vote form (Flask-WTF).
- [ ] Add per-IP rate limiting on `POST /vote` (Flask-Limiter).
- [ ] Validate `candidate` form field against the current candidate list (allow-list) before writing.
- [ ] Add security headers (CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy) via `flask-talisman` or manual `after_request`.
- [ ] Add `requirements.txt` with pinned versions.
- [ ] Custom error handlers (404/500) that don't leak stack traces.

## Medium Priority

- [ ] Unify candidate seed data into one place (currently duplicated between `app.py` and `scripts/data.py` with different schemas).
- [ ] Add basic automated tests (pytest + Flask test client) covering `GET /` and `POST /vote`, including invalid-candidate and concurrent-vote cases.
- [ ] Add structured logging for vote events (candidate, timestamp, source IP) for auditability.
- [ ] Move `JSON_FILE` path and other config into environment variables / a small config module.

## Low Priority

- [ ] Decide fate of `scripts/` (revive as a real CLI companion tool, or delete) — see DECISIONS.md open item.
- [ ] Improve `index.html` semantics/accessibility (labels, `aria-live` region for vote counts).
- [ ] Add a `/results` view separate from the voting view, if the project wants a public tally page.

## Future Improvements

- [ ] Optional migration path to SQLite if concurrent-write issues resist file-locking fixes at scale (explicitly out of scope for now — JSON persistence is intentional per README).
- [ ] Numeric-entry voting UI (candidate number instead of click), as already planned in the README's own roadmap note.
- [ ] Dockerfile + simple deployment doc, if the project moves beyond local dev.