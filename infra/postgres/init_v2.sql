CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    number INTEGER NOT NULL UNIQUE,
    party TEXT NOT NULL,
    votes_count INTEGER NOT NULL DEFAULT 0 CHECK (votes_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE voters_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    voter_hash TEXT NOT NULL UNIQUE,
    voted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_voters_registry_voter_hash ON voters_registry (voter_hash);

CREATE TABLE audit_chain (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seq BIGSERIAL UNIQUE NOT NULL,
    previous_hash TEXT,
    event_type TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL UNIQUE,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_chain_seq ON audit_chain (seq);

-- Least-privilege application role (do not use the superuser role from the app).
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_worker') THEN
        CREATE ROLE app_worker LOGIN PASSWORD 'CHANGE_ME_VIA_ENV_IN_PROD';
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE ON candidates TO app_worker;
GRANT SELECT, INSERT ON voters_registry TO app_worker;
GRANT SELECT, INSERT ON audit_chain TO app_worker;
-- No DELETE granted anywhere: audit_chain and voters_registry must be append-only.
-- candidates UPDATE restricted to votes_count in application logic (Phase 2/3).