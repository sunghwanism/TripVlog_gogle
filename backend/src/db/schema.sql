-- TripVlog AI Generator — Phase 01 Database Schema
-- PostgreSQL 15+

-- ─────────────────────────────────────────────
-- Table: users
-- Stores Google OAuth2 users with encrypted tokens
-- ─────────────────────────────────────────────
CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               VARCHAR(255) UNIQUE NOT NULL,
    display_name        VARCHAR(255),
    google_id           VARCHAR(255) UNIQUE NOT NULL,
    -- OAuth tokens encrypted at rest (AES-256-GCM)
    access_token_enc    BYTEA NOT NULL,
    refresh_token_enc   BYTEA NOT NULL,
    token_expires_at    TIMESTAMPTZ NOT NULL,
    encryption_key_id   VARCHAR(64) NOT NULL,  -- KMS key version reference
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_google_id ON users(google_id);

-- ─────────────────────────────────────────────
-- Table: projects
-- One project = one Google Drive folder + concept prompt
-- ─────────────────────────────────────────────
CREATE TABLE projects (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    folder_id           VARCHAR(255) NOT NULL,  -- Google Drive folder ID
    concept_prompt      TEXT NOT NULL,
    status              VARCHAR(32) NOT NULL DEFAULT 'CREATED'
                        CHECK (status IN (
                            'CREATED', 'INGESTING', 'ANALYZING', 'PLANNING',
                            'REFERENCING', 'GENERATING', 'AUDIO_SYNC',
                            'EXPORTING', 'COMPLETED', 'FAILED'
                        )),
    total_files         INTEGER DEFAULT 0,
    processed_files     INTEGER DEFAULT 0,
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_projects_status ON projects(status);

-- ─────────────────────────────────────────────
-- Table: media_files
-- One row per file ingested from Google Drive
-- ─────────────────────────────────────────────
CREATE TABLE media_files (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    drive_file_id       VARCHAR(255) NOT NULL,
    file_name           VARCHAR(512) NOT NULL,
    mime_type           VARCHAR(64) NOT NULL,
    file_size_bytes     BIGINT NOT NULL,
    gcs_path            VARCHAR(1024),  -- GCP Cloud Storage path (populated after upload)

    -- EXIF/XMP metadata (populated by ANALYZE worker)
    gps_lat             DOUBLE PRECISION,
    gps_lng             DOUBLE PRECISION,
    location_name       VARCHAR(512),   -- Reverse-geocoded from GPS
    captured_at         TIMESTAMPTZ,
    camera_info         VARCHAR(255),   -- "Make Model"
    orientation         SMALLINT,       -- EXIF Orientation value (1-8)

    -- Video-specific fields
    duration_ms         INTEGER,
    width               INTEGER,
    height              INTEGER,
    fps                 REAL,
    codec               VARCHAR(32),

    -- Processing state
    skip_reason         VARCHAR(255),   -- NULL if file was not skipped
    metadata_extracted  BOOLEAN NOT NULL DEFAULT FALSE,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_media_files_project_id ON media_files(project_id);
CREATE INDEX idx_media_files_captured_at ON media_files(project_id, captured_at);

-- ─────────────────────────────────────────────
-- Table: generation_jobs
-- Tracks each pipeline phase job per project
-- ─────────────────────────────────────────────
CREATE TABLE generation_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    phase           VARCHAR(32) NOT NULL
                    CHECK (phase IN (
                        'INGEST', 'ANALYZE', 'PLAN', 'REFERENCE',
                        'GENERATE', 'AUDIO', 'EXPORT'
                    )),
    status          VARCHAR(32) NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'RETRYING')),
    attempt_count   INTEGER NOT NULL DEFAULT 0,
    max_attempts    INTEGER NOT NULL DEFAULT 3,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_log       TEXT,
    worker_id       VARCHAR(128),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_generation_jobs_project_id ON generation_jobs(project_id);
CREATE INDEX idx_generation_jobs_status ON generation_jobs(status);
