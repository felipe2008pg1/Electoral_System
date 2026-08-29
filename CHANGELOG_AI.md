# CHANGELOG_AI.md

Chronological log of meaningful changes made by AI agents. Newest entries at the top.

---

## 2026-08-29 — V2 Phase 1: Docker/FastAPI/Redis/PostgreSQL skeleton

**Type:** New architecture scaffold (V2), V1 untouched

**Summary:**
Started implementation of the "Secure Electoral System V2" per owner-provided spec (FastAPI async, Redis queue, PostgreSQL, immutable audit chain, WebSocket results). This is a new project scope superseding V1's Flask/JSON architecture for this version — see DECISIONS.md #5.

**Files added:**
- `docker-compose.yml` — api, redis (AOF + password), postgres (healthchecks, no exposed ports by default)
- `backend/Dockerfile`, `backend/requirements.txt`, `backend/.env.example`
- `backend/app/core/config.py` — fail-fast pydantic settings (no default secrets)
- `backend/app/db/session.py` — async SQLAlchemy engine/session
- `backend/app/main.py` — FastAPI app with `/health` endpoint; `/docs` disabled outside debug
- `infra/postgres/init.sql` — schema for `candidates`, `voters_registry`, `audit_chain`; least-privilege `app_worker` role with no `DELETE` grants

**Security notes:**
- Flagged (not yet resolved): CPF has low entropy, so `sha256(cpf + salt)` is brute-forceable offline if the DB or salt leaks — recorded in DECISIONS.md and TODO.md as a Critical open item, not silently accepted.
- Redis configured with `--appendonly yes` and a required password from the start, not deferred to "later hardening."
- Postgres app role has no `DELETE` privilege on any table — audit/voter tables are append-only at the DB level.

**Not yet implemented (next phases):** background worker (ACID transaction + audit chain append), WebSocket broadcast, frontend, `POST /candidates` admin endpoint (candidates table currently has no write path — must be seeded manually or via a Phase-3 admin endpoint).

---

## 2026-08-29 — V2 Phase 2: CPF validation + POST /vote + Redis queue

**Type:** Feature (V2)

**Summary:** Implemented the request-side of the vote flow per spec section 4, steps 1–4.

**Files added:**
- `backend/app/core/security.py` — CPF format/checksum validation (mod-11 check digits, rejects repeated-digit sequences like `111.111.111-11`); `compute_voter_hash()` (HMAC-SHA256, keyed by `VOTER_HMAC_SECRET`).
- `backend/app/schemas/vote.py` — `VoteRequest`/`VoteAccepted` Pydantic models; CPF and candidate_number validated at the schema boundary before any handler code runs.
- `backend/app/db/models.py` — SQLAlchemy ORM models for `candidates`, `voters_registry`, `audit_chain`, matching `infra/postgres/init.sql`.
- `backend/app/core/redis_client.py` — pooled async Redis client.
- `backend/app/core/limiter.py` — `slowapi` Limiter backed by Redis (separated into its own module specifically to avoid a circular import between `main.py` and the vote router).
- `backend/app/api/routes/vote.py` — `POST /vote`: validates CPF, computes `voter_hash`, checks `voters_registry` for a duplicate (fast-path only — see below), checks candidate exists, pushes to Redis Stream `votes:pending` via `XADD`, returns `202` with a random `tracking_id`.
- `backend/app/main.py` — wired the vote router, global rate-limit exception handler, and a catch-all exception handler that logs full tracebacks server-side but returns a generic `{"detail": "Internal server error"}` to the client (no stack trace leakage).

**Security decisions made in this phase:**
- Raw CPF is never logged, persisted, or included in the queue payload — only `voter_hash` leaves the request handler.
- `tracking_id` returned to the client is a fresh random UUID, unrelated to `voter_hash`, so the client-visible tracking token can't be used to correlate back to the voter.
- The duplicate-vote check against `voters_registry` in `vote.py` is explicitly a **fast-path UX check, not the enforcement point** — under concurrent requests with the same CPF, both could pass this check before either is written. Real enforcement is the `voter_hash UNIQUE` constraint on `voters_registry`, which the worker (Phase 3) must handle by catching the DB conflict and treating it as a rejected duplicate, not a crash.
- Redis Stream (`XADD`) chosen over a plain list specifically so the Phase 3 worker can use consumer groups (`XREADGROUP`) with ack/retry — a worker crash mid-processing does not silently drop an accepted vote.
- `POST /vote` rate-limited to `5/minute` per IP via `slowapi` (Redis-backed, survives multi-instance deployment). Session-based limiting from the original spec is **not yet implemented** — no session/device-identity mechanism exists yet; added to TODO.md.

**Known gaps carried to TODO.md:** no write path exists yet for the `candidates` table (needs seeding or an admin endpoint); worker/consumer for `votes:pending` not implemented; WebSocket broadcast not implemented.

---

## 2026-08-29 — V2 Phase 3: Background worker + audit chain

**Type:** Feature (V2)

**Summary:** Implemented the consumer side of the vote flow per spec section 4, steps 5–6 (minus WebSocket broadcast, which is Phase 4).

**Files added:**
- `backend/app/worker/audit.py` — `compute_payload_hash()` and `compute_entry_hash()`, both using canonical (sorted-key) JSON serialization so hash inputs are deterministic regardless of dict ordering.
- `backend/app/worker/consumer.py` — `XREADGROUP`-based consumer on `votes:pending` (consumer group `vote_processors`). Per message: opens one DB transaction that takes a Postgres advisory lock (`pg_advisory_xact_lock`) to serialize audit-chain appends, inserts into `voters_registry` (flushed immediately so the `voter_hash` UNIQUE constraint is checked before proceeding — this is the real duplicate-vote enforcement point, not the API's fast-path check), atomically increments `candidates.votes_count` via a single `UPDATE ... RETURNING`, reads the previous `entry_hash`, computes and appends the new `audit_chain` row, commits, then `XACK`s the message. Includes `reclaim_stale()` (startup-time `XPENDING`/`XCLAIM` recovery for messages abandoned by a crashed worker) and dead-lettering to `votes:deadletter` after `MAX_DELIVERIES` (5) failed attempts.

**Files modified:**
- `infra/postgres/init.sql`, `backend/app/db/models.py` — added `audit_chain.seq` (monotonic ordering, avoids relying on `timestamp` which can collide under concurrency) and `audit_chain.entry_hash` (the row's own tamper-evident hash). **This is a correction to the owner's original spec**, not an addition requested by them — the original schema stored only `previous_hash`, with no column for the current row's hash, which means there would be nothing to verify a row against. Recorded as DECISIONS.md #4.
- `docker-compose.yml` — added `worker` service (same image as `api`, different command).

**Concurrency/integrity properties verified by unit test (hash functions only — no live DB/Redis in this sandbox):**
- `compute_payload_hash` is order-independent (same dict, different key order → same hash).
- `compute_entry_hash` produces different output for different chain positions.
- Changing any field feeding into `compute_entry_hash` changes its output (the actual tamper-detection property).
- Both worker and API modules import cleanly together (no circular imports).

**Not yet implemented:** WebSocket broadcast on commit (Phase 4), periodic (vs. startup-only) reclaim of stuck messages, a chain-verification script/endpoint, candidate seeding/admin write path.

## 2026-08-29 — Initial repository analysis and context setup

**Type:** Documentation / project setup (no application code changed)

**Summary:**
Performed initial read-only analysis of the repository (`app.py`, `scripts/`, `templates/`, `static/`, `README.md`). No source files were modified in this session.

**Findings recorded (see TODO.md for full list):**
- `templates/index.html` and `app.py` use mismatched variable/field names and routes — the web app currently does not function end-to-end.
- `scripts/tools.py` is corrupted (wrapped in a literal markdown fence) and unused by the running app.
- `scripts/` as a whole is an unfinished, disconnected CLI prototype with its own inconsistent data schema.
- No CSRF protection, no rate limiting, `debug=True`, no file-locking on `votes.json`, no `requirements.txt`, no tests.

**Files added:**
- `CLAUDE.md`
- `ARCHITECTURE.md`
- `TODO.md`
- `CHANGELOG_AI.md` (this file)
- `DECISIONS.md`

**Next steps:** Awaiting development instructions (Phase 3). First fix should be the critical template/app mismatch, since nothing else can be verified while the app is non-functional.