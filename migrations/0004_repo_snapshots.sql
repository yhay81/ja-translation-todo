-- Machine-collected GitHub metadata, kept separate from human/agent evidence.
CREATE TABLE repo_snapshots (
  repository TEXT PRIMARY KEY,
  stars INTEGER,
  pushed_at TEXT,
  archived INTEGER NOT NULL DEFAULT 0,
  license TEXT,
  default_branch TEXT,
  contributing_path TEXT,
  ja_activity_json TEXT,
  etag_repo TEXT,
  etag_community TEXT,
  etag_search TEXT,
  fetched_at INTEGER NOT NULL DEFAULT 0,
  error_count INTEGER NOT NULL DEFAULT 0,
  last_error TEXT
);
CREATE INDEX repo_snapshots_fetched ON repo_snapshots(fetched_at);
