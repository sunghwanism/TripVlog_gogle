# Phase 01: Data & Analysis — Backend Engineer

> **Conclusion:** Phase 01 establishes the data foundation — OAuth2-secured Google Drive ingestion, streaming file downloads with EXIF/XMP extraction, and a normalized PostgreSQL schema that feeds all downstream pipeline phases.

---

## 1. Google Drive Ingestion Pipeline

### 1.1 OAuth2 Flow

```
User clicks "Connect Google Drive"
  → Frontend redirects to Google OAuth2 consent screen
  → Google redirects to POST /api/auth/google/callback with auth code
  → Backend exchanges code for access_token + refresh_token
  → Tokens encrypted (AES-256-GCM) and stored in users table
  → JWT set in httpOnly + Secure + SameSite=Strict cookie (never in response body)
  → Frontend reads auth state from GET /api/auth/me (cookie sent automatically)
```

**Required OAuth2 Scopes (minimum necessary):**

| Scope | Purpose |
|-------|---------|
| `https://www.googleapis.com/auth/drive.readonly` | Read files/folders from user's Drive |
| `https://www.googleapis.com/auth/userinfo.email` | Identify user account |
| `https://www.googleapis.com/auth/userinfo.profile` | Display name in UI |

No `drive.file` or `drive` (full access) — we only need read-only access to enumerate and download media.

### 1.2 File Enumeration

```
POST /api/projects { folder_id, concept_prompt }
  → Validate folder_id exists and user has access
  → Queue INGEST job via BullMQ
  → INGEST worker:
      1. List all files in folder (paginated, nextPageToken)
      2. Filter by MIME type: image/jpeg, image/png, image/heic, video/mp4, video/quicktime
      3. Sort by createdTime (ascending) for chronological ordering
      4. Store file metadata in media_files table
```

**Google Drive API call pattern:**

```
GET https://www.googleapis.com/drive/v3/files
  ?q='${folderId}' in parents and trashed=false
  &fields=files(id,name,mimeType,size,createdTime,imageMediaMetadata,videoMediaMetadata)
  &pageSize=100
  &orderBy=createdTime
```

### 1.3 File Download Strategy

**Streaming download** (not batch) — each file is downloaded individually to limit memory:

| Criterion | Strategy |
|-----------|----------|
| Files < 50MB | Direct stream to GCP Cloud Storage via `drive.files.get({ alt: 'media' })` pipe |
| Files 50–500MB | Chunked download (8MB chunks) with resume capability |
| Files > 500MB | Skip with warning; log to `media_files.skip_reason` |
| Total folder limit | 5GB per project (soft limit, configurable via env) |

**Concurrency:** Max 3 parallel downloads per project to respect Google Drive API rate limits (12,000 requests/100s/user).

### 1.4 Supported Formats

| Format | Type | EXIF/XMP Support |
|--------|------|------------------|
| JPEG (.jpg, .jpeg) | Image | Full EXIF + XMP |
| PNG (.png) | Image | XMP only |
| HEIC (.heic) | Image | Full EXIF + XMP (via heic-decode) |
| MP4 (.mp4) | Video | MP4 metadata atoms + XMP sidecar |
| MOV (.mov) | Video | QuickTime metadata + XMP sidecar |

---

## 2. EXIF/XMP Metadata Extraction

### 2.1 Extraction Pipeline

After each file is downloaded to GCP Cloud Storage, a Python microservice extracts metadata:

```python
# Python microservice: metadata-extractor
# Libraries: exifread, python-xmp-toolkit, ffprobe-python

def extract_metadata(file_path: str, mime_type: str) -> dict:
    """Extract metadata — returns new dict, never mutates input."""
    if mime_type.startswith('image/'):
        return {
            **extract_exif(file_path),
            **extract_xmp(file_path),
        }
    elif mime_type.startswith('video/'):
        return {
            **extract_video_metadata(file_path),  # ffprobe
            **extract_xmp_sidecar(file_path),
        }
    return {}
```

### 2.2 Extracted Fields

| Field | Source | DB Column |
|-------|--------|-----------|
| GPS Latitude | EXIF GPSInfo | `media_files.gps_lat` |
| GPS Longitude | EXIF GPSInfo | `media_files.gps_lng` |
| Capture Timestamp | EXIF DateTimeOriginal | `media_files.captured_at` |
| Camera Make/Model | EXIF Make + Model | `media_files.camera_info` |
| Orientation | EXIF Orientation | `media_files.orientation` |
| Duration (video) | ffprobe format.duration | `media_files.duration_ms` |
| Resolution | EXIF/ffprobe | `media_files.width`, `media_files.height` |
| Frame Rate (video) | ffprobe r_frame_rate | `media_files.fps` |
| Codec (video) | ffprobe codec_name | `media_files.codec` |

### 2.3 GPS → Location Reverse Geocoding

For clips with GPS data, batch reverse-geocode using Google Maps Geocoding API (or OpenStreetMap Nominatim for cost savings):

```
media_files.gps_lat, media_files.gps_lng → media_files.location_name
Example: 37.5665, 126.9780 → "Seoul, South Korea"
```

This location data feeds the AI storyboard scene labeling in Phase 02.

---

## 3. Database Schema (Phase 01 Tables)

### 3.1 users

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    display_name    VARCHAR(255),
    google_id       VARCHAR(255) UNIQUE NOT NULL,
    -- OAuth tokens encrypted at rest (AES-256-GCM)
    access_token_enc    BYTEA NOT NULL,
    refresh_token_enc   BYTEA NOT NULL,
    token_expires_at    TIMESTAMPTZ NOT NULL,
    encryption_key_id   VARCHAR(64) NOT NULL,  -- KMS key version reference
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_google_id ON users(google_id);
```

### 3.2 projects

```sql
CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    folder_id       VARCHAR(255) NOT NULL,  -- Google Drive folder ID
    concept_prompt  TEXT NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'CREATED'
                    CHECK (status IN (
                        'CREATED', 'INGESTING', 'ANALYZING', 'PLANNING',
                        'REFERENCING', 'GENERATING', 'AUDIO_SYNC',
                        'EXPORTING', 'COMPLETED', 'FAILED'
                    )),
    total_files     INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_projects_status ON projects(status);
```

### 3.3 media_files

```sql
CREATE TABLE media_files (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    drive_file_id   VARCHAR(255) NOT NULL,
    file_name       VARCHAR(512) NOT NULL,
    mime_type       VARCHAR(64) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    gcs_path        VARCHAR(1024),  -- GCP Cloud Storage path

    -- EXIF/XMP metadata
    gps_lat         DOUBLE PRECISION,
    gps_lng         DOUBLE PRECISION,
    location_name   VARCHAR(512),
    captured_at     TIMESTAMPTZ,
    camera_info     VARCHAR(255),
    orientation     SMALLINT,

    -- Video-specific
    duration_ms     INTEGER,
    width           INTEGER,
    height          INTEGER,
    fps             REAL,
    codec           VARCHAR(32),

    -- Processing state
    skip_reason     VARCHAR(255),  -- NULL if not skipped
    metadata_extracted BOOLEAN NOT NULL DEFAULT FALSE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_media_files_project_id ON media_files(project_id);
CREATE INDEX idx_media_files_captured_at ON media_files(project_id, captured_at);
```

### 3.4 generation_jobs

```sql
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
```

---

## 4. Phase 01 API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/auth/google/callback` | Exchange OAuth2 code for tokens, create/update user |
| `POST` | `/api/projects` | Create project (folder_id + concept_prompt), queue INGEST |
| `GET`  | `/api/projects/:id` | Get project status + file count + metadata summary |
| `GET`  | `/api/projects/:id/files` | List ingested media_files with metadata |
| `GET`  | `/api/projects/:id/progress` | SSE stream for ingestion/analysis progress |

### Request/Response Validation (Zod)

```typescript
import { z } from 'zod'

const CreateProjectSchema = z.object({
  folder_id: z.string().min(1).max(255),
  concept_prompt: z.string().min(10).max(5000),
})

const ProjectIdParamSchema = z.object({
  id: z.string().uuid(),
})
```

---

## 5. Phase 01 Job Flow

```
[POST /api/projects]
  → Insert project row (status: CREATED)
  → Insert generation_job row (phase: INGEST, status: PENDING)
  → Enqueue BullMQ job: { projectId, phase: 'INGEST' }

[INGEST Worker]
  → Update job status: RUNNING
  → Enumerate Google Drive folder (paginated)
  → For each file:
      → Insert media_files row
      → Stream download to GCS
      → Update project.processed_files
      → Publish progress to Redis channel: project:{id}:progress
  → Update job status: COMPLETED
  → Enqueue next job: { projectId, phase: 'ANALYZE' }

[ANALYZE Worker]
  → For each media_file (metadata_extracted = false):
      → Call Python metadata-extractor microservice
      → Update media_files row with EXIF/XMP data
      → Batch reverse-geocode GPS coordinates
  → Update job status: COMPLETED
  → Enqueue next job: { projectId, phase: 'PLAN' }  (→ Phase 02)
```

---

## 6. Error Handling & Retry

| Error Type | Retry Strategy |
|------------|---------------|
| Google Drive API 429 (rate limit) | Exponential backoff: 1s, 2s, 4s, max 3 attempts |
| Google Drive API 5xx | Exponential backoff: 2s, 4s, 8s, max 3 attempts |
| File download timeout | Retry once after 30s, then skip with reason |
| Metadata extraction failure | Skip file, log error, continue pipeline |
| OAuth token expired | Auto-refresh via refresh_token, retry once |

Dead letter queue: Jobs exceeding max_attempts move to `dlq:ingest` for manual inspection.
