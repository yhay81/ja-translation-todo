-- Simplification: reporting moved to GitHub pull requests, cron removed,
-- authentication removed. The runtime keeps only the read-side catalog
-- (tasks / task_revisions / catalog_meta).

DROP TABLE IF EXISTS repo_snapshots;

DROP TABLE IF EXISTS reports;
DROP TABLE IF EXISTS lease_events;
DROP TABLE IF EXISTS claims;

DROP TABLE IF EXISTS user_profiles;
DROP TABLE IF EXISTS "passkey";
DROP TABLE IF EXISTS "oauth_consent";
DROP TABLE IF EXISTS "oauth_token";
DROP TABLE IF EXISTS "oauth_code";
DROP TABLE IF EXISTS "oauth_client";
DROP TABLE IF EXISTS "api_key";
DROP TABLE IF EXISTS "two_factor";
DROP TABLE IF EXISTS "verification";
DROP TABLE IF EXISTS "account";
DROP TABLE IF EXISTS "session";
DROP TABLE IF EXISTS "user";
