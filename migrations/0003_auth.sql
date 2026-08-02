CREATE TABLE IF NOT EXISTS "user" (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  email_verified INTEGER NOT NULL DEFAULT 0,
  name TEXT,
  image TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS "session" (
  id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  user_id TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL,
  ip_address TEXT,
  user_agent TEXT,
  last_active_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS session_user_id ON "session"(user_id);
CREATE TABLE IF NOT EXISTS "account" (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  provider_id TEXT NOT NULL,
  account_id TEXT NOT NULL,
  password_hash TEXT,
  access_token TEXT,
  refresh_token TEXT,
  expires_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (provider_id, account_id)
);
CREATE INDEX IF NOT EXISTS account_user_id ON "account"(user_id);
CREATE TABLE IF NOT EXISTS "verification" (
  id TEXT PRIMARY KEY,
  identifier TEXT NOT NULL,
  value_hash TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS verification_identifier_value_hash
  ON "verification"(identifier, value_hash);
CREATE TABLE IF NOT EXISTS "two_factor" (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL UNIQUE REFERENCES "user"(id) ON DELETE CASCADE,
  secret TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 0,
  last_used_step INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS "api_key" (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  name TEXT,
  prefix TEXT NOT NULL,
  key_hash TEXT NOT NULL UNIQUE,
  scopes TEXT,
  expires_at TEXT,
  enabled INTEGER NOT NULL DEFAULT 1,
  last_used_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS api_key_user_id ON "api_key"(user_id);
CREATE TABLE IF NOT EXISTS "oauth_client" (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL UNIQUE,
  client_secret_hash TEXT,
  name TEXT,
  redirect_uris TEXT NOT NULL,
  token_endpoint_auth_method TEXT NOT NULL,
  grant_types TEXT NOT NULL,
  scope TEXT,
  dpop_bound_access_tokens INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS "oauth_code" (
  id TEXT PRIMARY KEY,
  code_hash TEXT NOT NULL UNIQUE,
  client_id TEXT NOT NULL,
  user_id TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  grant_id TEXT NOT NULL,
  redirect_uri TEXT NOT NULL,
  scope TEXT,
  code_challenge TEXT NOT NULL,
  code_challenge_method TEXT NOT NULL DEFAULT 'S256',
  resource TEXT,
  dpop_jkt TEXT,
  used INTEGER NOT NULL DEFAULT 0,
  family_id TEXT,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS oauth_code_user_client ON "oauth_code"(user_id, client_id);
CREATE TABLE IF NOT EXISTS "oauth_token" (
  id TEXT PRIMARY KEY,
  access_token_hash TEXT NOT NULL UNIQUE,
  refresh_token_hash TEXT UNIQUE,
  family_id TEXT NOT NULL,
  client_id TEXT NOT NULL,
  user_id TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  grant_id TEXT NOT NULL,
  scope TEXT,
  resource TEXT,
  dpop_jkt TEXT,
  access_expires_at TEXT NOT NULL,
  refresh_expires_at TEXT,
  revoked INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS oauth_token_family_id ON "oauth_token"(family_id);
CREATE INDEX IF NOT EXISTS oauth_token_user_client ON "oauth_token"(user_id, client_id);
CREATE TABLE IF NOT EXISTS "oauth_consent" (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  client_id TEXT NOT NULL,
  grant_id TEXT NOT NULL,
  scope TEXT,
  revoked INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (user_id, client_id)
);
CREATE TABLE IF NOT EXISTS "passkey" (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  name TEXT,
  credential_id TEXT NOT NULL UNIQUE,
  public_key TEXT NOT NULL,
  counter INTEGER NOT NULL DEFAULT 0,
  device_type TEXT,
  backed_up INTEGER NOT NULL DEFAULT 0,
  transports TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS passkey_user_id ON "passkey"(user_id);

-- Application profile layer on top of hayate-auth users.
CREATE TABLE user_profiles (
  user_id TEXT PRIMARY KEY REFERENCES "user"(id) ON DELETE CASCADE,
  github_login TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL DEFAULT 'contributor' CHECK (role IN ('contributor','admin')),
  created_at INTEGER NOT NULL
);
