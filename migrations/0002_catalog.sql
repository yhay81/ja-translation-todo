-- Dynamic catalog: D1 becomes the runtime source of truth.
-- git catalog/tasks/*.json is demoted to seed / export / audit.

CREATE TABLE catalog_meta (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  catalog_revision TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);
INSERT INTO catalog_meta (id, catalog_revision, updated_at) VALUES (1, 'cat_bootstrap', 0);

CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('verification','translation','maintenance')),
  status TEXT NOT NULL CHECK (status IN
    ('needs_verification','ready','ask_first','in_progress','blocked','done','stale')),
  repository TEXT NOT NULL,
  category TEXT NOT NULL,
  title_ja TEXT NOT NULL,
  automation_level TEXT NOT NULL,
  search_text TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  task_revision INTEGER NOT NULL DEFAULT 1,
  published INTEGER NOT NULL DEFAULT 1 CHECK (published IN (0,1)),
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX tasks_status_updated ON tasks(status, updated_at DESC);
CREATE INDEX tasks_repository ON tasks(repository);

CREATE TABLE task_revisions (
  task_id TEXT NOT NULL REFERENCES tasks(id),
  task_revision INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  change_kind TEXT NOT NULL CHECK (change_kind IN
    ('create','update','status_change','auto_refresh','promote','import')),
  changed_by TEXT NOT NULL,
  change_note TEXT,
  created_at INTEGER NOT NULL,
  PRIMARY KEY (task_id, task_revision)
);
CREATE INDEX task_revisions_created ON task_revisions(created_at DESC);

-- Coordination v2: claims are short leases, so a rebuild is safe.
-- Claims gain a principal (agent API key or human session) and switch the
-- consistency token from the global catalog_revision to per-task revisions.
DROP TABLE IF EXISTS reports;
DROP TABLE IF EXISTS lease_events;
DROP TABLE IF EXISTS claims;

CREATE TABLE claims (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  principal_type TEXT NOT NULL CHECK (principal_type IN ('agent','user')),
  principal_id TEXT NOT NULL,
  owner_user_id TEXT,
  agent_label TEXT,
  idempotency_key TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  claim_token_hash TEXT NOT NULL,
  task_revision INTEGER NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('active','released','completed','expired')),
  lease_expires_at INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  release_idempotency_key TEXT,
  release_request_hash TEXT,
  release_reason TEXT,
  UNIQUE (principal_id, idempotency_key)
);
CREATE UNIQUE INDEX one_active_claim_per_task ON claims(task_id) WHERE state = 'active';
CREATE INDEX claims_task_created ON claims(task_id, created_at DESC);
CREATE INDEX claims_owner ON claims(owner_user_id, created_at DESC);

CREATE TABLE lease_events (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL REFERENCES claims(id),
  idempotency_key TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  lease_expires_at INTEGER NOT NULL,
  applied INTEGER NOT NULL DEFAULT 0 CHECK (applied IN (0,1)),
  created_at INTEGER NOT NULL,
  UNIQUE (claim_id, idempotency_key)
);

CREATE TABLE reports (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL REFERENCES claims(id),
  idempotency_key TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  review_state TEXT NOT NULL DEFAULT 'pending'
    CHECK (review_state IN ('pending','approved','rejected')),
  reviewed_by TEXT,
  reviewed_at INTEGER,
  review_note TEXT,
  created_at INTEGER NOT NULL,
  UNIQUE (claim_id, idempotency_key)
);
CREATE INDEX reports_claim_created ON reports(claim_id, created_at DESC);
CREATE INDEX reports_review_state ON reports(review_state, created_at DESC);
