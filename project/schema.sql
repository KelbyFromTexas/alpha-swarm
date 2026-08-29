-- ALPHA SWARM canonical DDL (SQLite)
-- Types adapted from Postgres: BIGSERIAL→INTEGER PRIMARY KEY AUTOINCREMENT,
-- TIMESTAMPTZ→TEXT ISO8601, UUID→TEXT, JSONB→TEXT, NUMERIC→REAL.

CREATE TABLE signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  observed_at TEXT NOT NULL,
  source TEXT NOT NULL,
  topic_key TEXT NOT NULL,
  raw_term TEXT NOT NULL,
  volume REAL,
  velocity REAL,
  accel REAL,
  sentiment REAL,
  citations TEXT,
  raw TEXT
);
CREATE INDEX idx_signals_topic_time ON signals (topic_key, observed_at DESC);

CREATE TABLE candidates (
  id TEXT PRIMARY KEY,
  topic_key TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  breakout_at TEXT,
  status TEXT NOT NULL,
  scores TEXT,
  composite REAL,
  adversary_verdict TEXT,
  design TEXT,
  kill_reason TEXT
);

CREATE TABLE launches (
  id TEXT PRIMARY KEY,
  candidate_id TEXT REFERENCES candidates(id),
  mint TEXT UNIQUE,
  venue TEXT NOT NULL,
  launched_at TEXT NOT NULL,
  dev_buy_sol REAL NOT NULL,
  tx_signature TEXT NOT NULL,
  exit_policy TEXT NOT NULL
);

CREATE TABLE outcomes (
  launch_id TEXT REFERENCES launches(id),
  measured_at TEXT,
  ath_mcap_usd REAL,
  mcap_usd REAL,
  holders INTEGER,
  volume_24h_usd REAL,
  realized_pnl_sol REAL,
  verdict TEXT
);

CREATE TABLE bus_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  "from" TEXT NOT NULL,
  "to" TEXT NOT NULL,
  candidate_id TEXT,
  payload TEXT NOT NULL,
  model TEXT,
  tokens INTEGER,
  latency_ms INTEGER,
  citations TEXT
);
