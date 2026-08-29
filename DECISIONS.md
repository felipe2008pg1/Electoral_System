# DECISIONS.md

Record of important technical decisions. Each entry: Decision, Reason, Consequences.

---

## 1. Keep Flask + JSON-file persistence (no database migration)

**Decision:** Retain the current architecture — Flask app, JSON file for storage — rather than migrating to SQLite/Postgres.

**Reason:** Explicitly stated in the project's own README as an intentional architectural choice for studying Flask/Python/JSON, and the project owner asked to evolve the existing project rather than rebuild it. No functional requirement currently demands a database.

**Consequences:** Concurrency safety must be handled manually (file locking) rather than relying on DB transactions. Scalability beyond a single-process local server is limited — acceptable for the project's stated academic scope. A future migration to SQLite is listed as an optional future improvement (TODO.md) if concurrency issues become a real problem.

---

## 2. Treat `scripts/` as legacy/dead code, not delete it yet

**Decision:** Do not remove the `scripts/` directory during initial cleanup, despite it being disconnected from the running app and containing a corrupted file (`tools.py`).

**Reason:** Cannot determine from the repository alone whether the project owner intends to revive this as a companion CLI tool or considers it abandoned. Removing code without confirmation risks losing intended functionality.

**Consequences:** `scripts/` remains in the repo, flagged in TODO.md as needing an explicit decision. It must continue to be treated as non-authoritative and must not be assumed correct or in use by AI agents working on this project.

---

## 3. Single canonical data schema: `{"candidate": str, "votes": int}`

**Decision:** Standardize on the English-key schema already used by `app.py` and `votes.json`, rather than the Portuguese-key schema (`candidato`/`votos`) found in `templates/index.html` and `scripts/data.py`.

**Reason:** `app.py` is the actual running application and its schema is what persists to disk today; the README is in English; the Portuguese-key usages are leftovers from an incomplete translation pass.

**Consequences:** `templates/index.html` must be corrected to match this schema (tracked as a Critical item in TODO.md). Any future work must not reintroduce the Portuguese keys.

---

## 4. `audit_chain` schema corrected: added `entry_hash` and `seq`

**Decision:** The owner's original spec defined `audit_chain` with only `previous_hash`, `event_type`, `payload_hash`, `timestamp` — no column stores the hash of the current row itself. Added `entry_hash` (the row's own tamper-evident hash) and `seq` (monotonic ordering column) not present in the original spec.

**Reason:** Without a stored `entry_hash`, "tamper-evident chain" has nothing to verify against — you'd need to recompute a row's hash from its own fields to check it, which is circular and doesn't detect tampering of that row's fields themselves. `seq` avoids depending on `timestamp` (which can collide under concurrent inserts) to determine chain order.

**Consequences:** Every audit row now stores `entry_hash = hash(previous_hash + event_type + payload_hash + timestamp)`, and the next row's `previous_hash` is the prior row's `entry_hash`. Verifying the whole chain means recomputing each row's hash from its own fields and confirming it matches both the stored `entry_hash` and the next row's `previous_hash`. Chain appends across concurrent worker processes are serialized via `pg_advisory_xact_lock` to prevent two workers reading the same "last hash" and forking the chain.

## 5. V1 (Flask/JSON) superseded by V2 (FastAPI/Redis/PostgreSQL) — new project, not an incremental change

**Decision:** Build a new "Secure Electoral System V2" per the owner's system design spec (FastAPI, async, Redis queue, PostgreSQL, immutable audit chain, WebSocket live results, Docker Compose). This supersedes Decision #1 (Flask + JSON persistence) for this new version.

**Reason:** Explicit new requirements from the project owner: high concurrency, tamper-evident audit trail, real-time results — none of which the V1 architecture (single-process Flask + flat JSON file) can satisfy. Confirmed as a new project scope, not an incremental evolution of V1.

**Consequences:** V1 (`app.py`, `templates/`, `static/`, `scripts/`) is left untouched under Decision #1/#2 pending explicit confirmation of its fate — it is not deleted. V2 lives in `backend/` + `infra/` + root `docker-compose.yml`. All future AI sessions must treat V2 as a separate architecture with its own rules (see CLAUDE.md V2 addendum, to be added as Phase 2/3 land).

**Security caveat recorded, not yet resolved:** the spec's `voter_hash = sha256(cpf + SECRET_SALT)` scheme does not provide real anonymity against a determined attacker, because CPF has very low entropy (~10⁹ valid values after checksum). A static salt/HMAC key raises the cost of brute-forcing the mapping but does not eliminate it. This is flagged in TODO.md as a Critical item to revisit before this system is treated as "anonymous" in any real sense — currently accepted as a known limitation for the academic/simulation scope of this project.

## Open items requiring project-owner input

- Fate of `scripts/` directory (revive vs. delete) — no decision made yet, reason cannot be inferred from repo alone.