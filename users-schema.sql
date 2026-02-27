-- ============================================================
-- REVODA — Users & Authentication Schema
-- ADD THIS TO YOUR EXISTING schema.sql
-- ============================================================

CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Authentication
    email               TEXT NOT NULL UNIQUE,
    password_hash       TEXT NOT NULL,

    -- Personal details
    first_name          TEXT NOT NULL,
    last_name           TEXT NOT NULL,
    phone               TEXT,

    -- Organisation
    org_name            TEXT NOT NULL,
    org_type            TEXT NOT NULL,
    -- cso | media | academic | legal | inec
    state               TEXT NOT NULL,

    -- Account status
    status              TEXT NOT NULL DEFAULT 'pending',
    -- pending | approved | suspended
    role                TEXT NOT NULL DEFAULT 'partner',
    -- partner | admin

    -- API access
    api_token_hash      TEXT,           -- SHA-256 of raw token
    api_token_prefix    TEXT,           -- first 12 chars shown in UI

    -- Email verification
    email_verified      BOOLEAN DEFAULT FALSE,
    email_verify_token  TEXT,

    -- Password reset
    pw_reset_token      TEXT,
    pw_reset_expires    TIMESTAMPTZ,

    -- Approval tracking
    approved_at         TIMESTAMPTZ,
    approved_by         TEXT,           -- admin email who approved

    -- Timestamps
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    last_login_at       TIMESTAMPTZ,

    CONSTRAINT valid_org_type CHECK (org_type IN ('cso','media','academic','legal','inec')),
    CONSTRAINT valid_status   CHECK (status   IN ('pending','approved','suspended')),
    CONSTRAINT valid_role     CHECK (role     IN ('partner','admin'))
);

CREATE INDEX idx_users_email  ON users(email);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_org    ON users(org_name);

-- Auto-update updated_at
CREATE TRIGGER trg_users_updated
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── Seed: EiE Nigeria admin account ──────────────────────────────────────────
-- Change this password immediately after first login!
-- Password below is: Admin2027!
INSERT INTO users (
    email, password_hash, first_name, last_name,
    org_name, org_type, state, status, role, email_verified
) VALUES (
    'admin@eienigeria.org',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TqUdoRSGRsHk2FTq3EIcHPaGe4Aq', -- bcrypt of "Admin2027!"
    'EiE', 'Nigeria Admin',
    'Enough is Enough Nigeria', 'cso', 'National',
    'approved', 'admin', TRUE
);

-- ── Session / audit log table ────────────────────────────────────────────────
CREATE TABLE user_sessions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    ip_address  TEXT,
    user_agent  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id);

-- ── Notifications table ──────────────────────────────────────────────────────
CREATE TABLE user_notifications (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    type        TEXT DEFAULT 'info', -- info | alert | success | warning
    read        BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notifs_user ON user_notifications(user_id, read);
