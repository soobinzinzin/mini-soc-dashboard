-- =============================================================================
-- Mini-SOC PostgreSQL Schema Initialization
-- Database: minisoc
-- =============================================================================

-- 1. Sensors Table
CREATE TABLE IF NOT EXISTS sensors (
    sensor_id TEXT PRIMARY KEY,
    site TEXT NOT NULL,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Raw Alerts Table (Ingested Telemetry)
CREATE TABLE IF NOT EXISTS raw_alerts (
    telemetry_id UUID PRIMARY KEY,
    sensor_id TEXT NOT NULL REFERENCES sensors(sensor_id),
    site TEXT NOT NULL,
    gid INT NOT NULL,
    sid INT NOT NULL,
    rev INT,
    signature TEXT NOT NULL,
    priority INT NOT NULL DEFAULT 0,
    protocol TEXT NOT NULL,
    src_ip INET,
    src_port INT,
    dst_ip INET,
    dst_port INT,
    raw_log TEXT NOT NULL,
    alert_timestamp TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for efficient querying and aggregation
CREATE INDEX IF NOT EXISTS idx_raw_alerts_site_timestamp ON raw_alerts (site, alert_timestamp);
CREATE INDEX IF NOT EXISTS idx_raw_alerts_sid ON raw_alerts (sid);

-- 3. Incidents Table (Aggregated / Correlated Events for Alert Engine)
CREATE TABLE IF NOT EXISTS incidents (
    id BIGSERIAL PRIMARY KEY,
    site TEXT NOT NULL,
    sid INT NOT NULL,
    src_ip TEXT,
    severity TEXT NOT NULL,
    alert_count INT NOT NULL DEFAULT 1,
    first_alert_at TIMESTAMPTZ NOT NULL,
    last_alert_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast correlation lookup: find open incidents matching (site, sid, src_ip)
CREATE INDEX IF NOT EXISTS idx_incidents_correlation
    ON incidents (site, sid, src_ip, status) WHERE status = 'open';

-- 4. Notifications Table (Dispatch records for Telegram / Webhook)
CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY,
    incident_id BIGINT REFERENCES incidents(id),
    channel TEXT NOT NULL,
    sent_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending'
);

-- 5. Admin Users Table (For future authentication)
CREATE TABLE IF NOT EXISTS admin_users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
