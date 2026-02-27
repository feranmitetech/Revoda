-- ============================================================
-- REVODA Election Incident Dashboard — Database Schema
-- PostgreSQL 15+ with PostGIS extension
-- EiE Nigeria · Civic Intelligence Platform
-- ============================================================

-- Enable PostGIS for geospatial queries
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm; -- for text search


-- ============================================================
-- ELECTIONS
-- Track multiple election cycles for historical comparison
-- ============================================================

CREATE TABLE elections (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL,          -- e.g. "2027 General Election"
    election_type TEXT NOT NULL,        -- presidential, governorship, senatorial
    scheduled_date DATE NOT NULL,
    phase       TEXT NOT NULL DEFAULT 'pre_election',
                -- pre_election | election_day | collation | post_election
    is_active   BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Only one active election at a time
CREATE UNIQUE INDEX idx_one_active_election ON elections (is_active)
    WHERE is_active = TRUE;


-- ============================================================
-- GEOLOCATION REFERENCE
-- Nigeria's administrative hierarchy: State → LGA → Ward → PU
-- ============================================================

CREATE TABLE states (
    code        CHAR(2) PRIMARY KEY,   -- e.g. LA, RV, KN
    name        TEXT NOT NULL UNIQUE,
    geom        GEOMETRY(MULTIPOLYGON, 4326)
);

CREATE TABLE lgas (
    id          SERIAL PRIMARY KEY,
    state_code  CHAR(2) REFERENCES states(code),
    name        TEXT NOT NULL,
    geom        GEOMETRY(MULTIPOLYGON, 4326),
    UNIQUE(state_code, name)
);

CREATE TABLE wards (
    id          SERIAL PRIMARY KEY,
    lga_id      INT REFERENCES lgas(id),
    name        TEXT NOT NULL,
    geom        GEOMETRY(MULTIPOLYGON, 4326)
);

CREATE TABLE polling_units (
    id              SERIAL PRIMARY KEY,
    code            TEXT UNIQUE NOT NULL,    -- e.g. "LG-IKJ-031"
    name            TEXT NOT NULL,
    ward_id         INT REFERENCES wards(id),
    address         TEXT,
    latitude        FLOAT8,
    longitude       FLOAT8,
    geom            GEOMETRY(POINT, 4326)
        GENERATED ALWAYS AS (
            CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL
            THEN ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
            END
        ) STORED,
    registered_voters INT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pu_geom ON polling_units USING GIST(geom);
CREATE INDEX idx_pu_code ON polling_units(code);


-- ============================================================
-- INCIDENTS — Core table
-- ============================================================

CREATE TABLE incidents (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    election_id         UUID REFERENCES elections(id),

    -- Classification
    category            TEXT NOT NULL,
    -- electoral_officials_arrival | material_availability | voting_irregularity
    -- vote_counting | result_announcement | violence
    -- police_behaviour | results_verification

    sub_category        TEXT,
    description         TEXT NOT NULL,
    severity            TEXT DEFAULT 'medium',  -- low | medium | high | critical

    -- Location (hierarchical — filled as much as known)
    state               TEXT NOT NULL,
    lga                 TEXT,
    ward                TEXT,
    polling_unit_code   TEXT REFERENCES polling_units(code),
    address_detail      TEXT,              -- free text additional detail

    -- Geospatial (auto-populated from PU code if not provided)
    latitude            FLOAT8,
    longitude           FLOAT8,
    geom                GEOMETRY(POINT, 4326)
        GENERATED ALWAYS AS (
            CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL
            THEN ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
            END
        ) STORED,

    -- Reporter (anonymised)
    reporter_type       TEXT NOT NULL,
    -- citizen | party_agent | observer | journalist | inec_official | partner
    reporter_anon_hash  TEXT,           -- one-way HMAC, no raw identity stored
    source_partner      TEXT,           -- org name for partner submissions

    -- Verification workflow
    status              TEXT NOT NULL DEFAULT 'unverified',
    -- unverified → verified | escalated | dismissed
    verification_notes  TEXT,
    verified_by_partner TEXT,
    verified_at         TIMESTAMPTZ,

    -- Media evidence
    media_urls          JSONB DEFAULT '[]',  -- array of S3 URLs

    -- Timestamps
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_category CHECK (category IN (
        'electoral_officials_arrival','material_availability',
        'voting_irregularity','vote_counting','result_announcement',
        'violence','police_behaviour','results_verification'
    )),
    CONSTRAINT valid_status CHECK (status IN (
        'unverified','verified','escalated','dismissed'
    )),
    CONSTRAINT valid_reporter_type CHECK (reporter_type IN (
        'citizen','party_agent','observer','journalist','inec_official','partner'
    ))
);

-- Performance indexes
CREATE INDEX idx_incidents_state      ON incidents(state);
CREATE INDEX idx_incidents_lga        ON incidents(lga);
CREATE INDEX idx_incidents_category   ON incidents(category);
CREATE INDEX idx_incidents_status     ON incidents(status);
CREATE INDEX idx_incidents_created    ON incidents(created_at DESC);
CREATE INDEX idx_incidents_election   ON incidents(election_id);
CREATE INDEX idx_incidents_geom       ON incidents USING GIST(geom);
-- Composite for common dashboard query
CREATE INDEX idx_incidents_state_cat  ON incidents(state, category, status);
-- Full-text search on description
CREATE INDEX idx_incidents_fts        ON incidents USING GIN(to_tsvector('english', description));

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_incidents_updated
    BEFORE UPDATE ON incidents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ============================================================
-- ESCALATION ALERTS
-- Generated automatically or by partners
-- ============================================================

CREATE TABLE alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_type      TEXT NOT NULL,
    -- hotspot_detected | violence_cluster | materials_failure | results_anomaly
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    state           TEXT NOT NULL,
    lga             TEXT,
    severity        TEXT NOT NULL DEFAULT 'medium',
    related_incident_ids UUID[],
    acknowledged    BOOLEAN DEFAULT FALSE,
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_alerts_state    ON alerts(state);
CREATE INDEX idx_alerts_created  ON alerts(created_at DESC);
CREATE INDEX idx_alerts_ack      ON alerts(acknowledged) WHERE acknowledged = FALSE;


-- ============================================================
-- PARTNER ORGANISATIONS
-- CSO coalitions, observer groups, media houses
-- ============================================================

CREATE TABLE partners (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_name        TEXT NOT NULL UNIQUE,
    org_type        TEXT,  -- cso | observer | media | academic | inec
    contact_email   TEXT,
    api_token_hash  TEXT NOT NULL,  -- bcrypt hash, never store raw token
    permissions     JSONB DEFAULT '{"submit": true, "verify": false, "escalate": false}',
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================
-- HISTORICAL INCIDENTS
-- Imported from previous elections for pattern comparison
-- ============================================================

CREATE TABLE historical_incidents (
    id              SERIAL PRIMARY KEY,
    election_year   INT NOT NULL,
    election_type   TEXT NOT NULL,
    category        TEXT NOT NULL,
    state           TEXT NOT NULL,
    lga             TEXT,
    ward            TEXT,
    polling_unit_code TEXT,
    description     TEXT,
    notes           TEXT,
    verified        BOOLEAN DEFAULT TRUE,
    source          TEXT,   -- which org documented this
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_hist_location  ON historical_incidents(state, lga, category);
CREATE INDEX idx_hist_year      ON historical_incidents(election_year);


-- ============================================================
-- VIEWS for dashboard
-- ============================================================

-- Real-time national summary
CREATE MATERIALIZED VIEW mv_national_stats AS
SELECT
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE status = 'unverified') AS unverified,
    COUNT(*) FILTER (WHERE status = 'verified') AS verified,
    COUNT(*) FILTER (WHERE status = 'escalated') AS escalated,
    COUNT(*) FILTER (WHERE category = 'violence') AS violence_count,
    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') AS last_hour,
    NOW() AS last_refreshed
FROM incidents;

-- Refresh every 60 seconds (call from cron or background task)
CREATE UNIQUE INDEX ON mv_national_stats (last_refreshed);

-- Per-state summary
CREATE MATERIALIZED VIEW mv_state_stats AS
SELECT
    state,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE status = 'escalated') AS escalated,
    COUNT(*) FILTER (WHERE category = 'violence') AS violence,
    MAX(created_at) AS latest_incident
FROM incidents
GROUP BY state;

CREATE UNIQUE INDEX ON mv_state_stats (state);


-- ============================================================
-- SEED: Active election
-- ============================================================

INSERT INTO elections (name, election_type, scheduled_date, phase, is_active)
VALUES (
    '2027 Nigeria General Election',
    'presidential_governorship',
    '2027-02-20',
    'pre_election',
    TRUE
);
