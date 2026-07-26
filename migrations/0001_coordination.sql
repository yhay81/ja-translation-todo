CREATE TABLE IF NOT EXISTS claims (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  claim_token_hash TEXT NOT NULL,
  catalog_revision TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('active', 'released', 'completed', 'expired')),
  lease_expires_at INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  release_idempotency_key TEXT,
  release_request_hash TEXT,
  release_reason TEXT,
  UNIQUE (agent_id, idempotency_key)
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_claim_per_task
  ON claims(task_id)
  WHERE state = 'active';

CREATE INDEX IF NOT EXISTS claims_task_created
  ON claims(task_id, created_at DESC);

CREATE TABLE IF NOT EXISTS lease_events (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL REFERENCES claims(id),
  idempotency_key TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  lease_expires_at INTEGER NOT NULL,
  applied INTEGER NOT NULL DEFAULT 0 CHECK (applied IN (0, 1)),
  created_at INTEGER NOT NULL,
  UNIQUE (claim_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL REFERENCES claims(id),
  idempotency_key TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  UNIQUE (claim_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS reports_claim_created
  ON reports(claim_id, created_at DESC);
