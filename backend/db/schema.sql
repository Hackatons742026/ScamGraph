PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, status TEXT NOT NULL, started_at TEXT NOT NULL,
  finished_at TEXT, summary_json TEXT NOT NULL DEFAULT '{}', error TEXT
);
CREATE TABLE IF NOT EXISTS incidents (
  id TEXT PRIMARY KEY, folder TEXT NOT NULL, title TEXT, first_seen TEXT,
  last_seen TEXT, coverage_json TEXT NOT NULL DEFAULT '{}', status TEXT,
  ingested_at TEXT
);
CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY, incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
  kind TEXT NOT NULL, path TEXT NOT NULL, funnel_step INTEGER, role TEXT,
  sha256 TEXT, captured_at TEXT, parser TEXT, parse_status TEXT, error TEXT
);
CREATE INDEX IF NOT EXISTS idx_artifacts_incident ON artifacts(incident_id);
CREATE TABLE IF NOT EXISTS pages (
  id INTEGER PRIMARY KEY, artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
  url_redacted TEXT, final_url TEXT, domain TEXT, title TEXT, role TEXT
);
CREATE TABLE IF NOT EXISTS requests (
  id INTEGER PRIMARY KEY, artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
  seq INTEGER, method TEXT, host TEXT, path_pattern TEXT, status INTEGER,
  server_ip TEXT, mime TEXT, body_sha1 TEXT
);
CREATE TABLE IF NOT EXISTS media (
  id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
  kind TEXT NOT NULL, sha256 TEXT NOT NULL, path TEXT, phash TEXT,
  frame_ts REAL, ocr_text TEXT
);
CREATE TABLE IF NOT EXISTS evidence (
  id INTEGER PRIMARY KEY, incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
  artifact_id TEXT REFERENCES artifacts(id) ON DELETE SET NULL, type TEXT NOT NULL,
  family TEXT, tier TEXT NOT NULL, value_hash TEXT NOT NULL, display_value TEXT NOT NULL,
  weight REAL NOT NULL DEFAULT 0, funnel_step INTEGER, ignored INTEGER NOT NULL DEFAULT 0,
  ignore_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_evidence_value ON evidence(type, value_hash);
CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_observation ON evidence(
  incident_id, type, value_hash, COALESCE(artifact_id, ''), COALESCE(funnel_step, -1)
);
CREATE TABLE IF NOT EXISTS edges (
  id TEXT PRIMARY KEY, a_incident TEXT NOT NULL REFERENCES incidents(id),
  b_incident TEXT NOT NULL REFERENCES incidents(id), level TEXT NOT NULL, score REAL NOT NULL,
  comparable INTEGER NOT NULL, evidence_json TEXT NOT NULL, status TEXT
);
CREATE TABLE IF NOT EXISTS campaigns (
  id TEXT PRIMARY KEY, level TEXT NOT NULL, label TEXT NOT NULL,
  profile_json TEXT NOT NULL DEFAULT '{}', first_seen TEXT, last_seen TEXT
);
CREATE TABLE IF NOT EXISTS membership (
  campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
  reason_json TEXT NOT NULL DEFAULT '{}', PRIMARY KEY(campaign_id, incident_id)
);
CREATE TABLE IF NOT EXISTS decisions (
  incident_id TEXT PRIMARY KEY REFERENCES incidents(id) ON DELETE CASCADE,
  outcome TEXT NOT NULL, campaign_id TEXT REFERENCES campaigns(id),
  reasons_json TEXT NOT NULL, decided_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, action TEXT NOT NULL,
  subject_id TEXT, detail_json TEXT NOT NULL DEFAULT '{}'
);
