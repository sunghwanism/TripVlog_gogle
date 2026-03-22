# Backend Architecture — Complete Design

> **Conclusion:** The backend is a Node.js API gateway fronting Python microservices for compute-heavy tasks, with BullMQ orchestrating a 7-phase async pipeline. PostgreSQL stores persistent state, Redis handles job queues and real-time progress, and GCP Cloud Storage bridges all file I/O between phases.

---

## Table of Contents

1. [API Endpoints](#1-api-endpoints)
2. [Data Ingestion Pipeline](#2-data-ingestion-pipeline)
3. [Database Schema](#3-database-schema)
4. [Async Job Architecture](#4-async-job-architecture)
5. [Temporal Pacing Logic](#5-temporal-pacing-logic)
6. [Security](#6-security)

---

## 1. API Endpoints

### 1.1 REST Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/auth/google/callback` | Public | OAuth2 code exchange → JWT session |
| `GET`  | `/api/auth/me` | JWT | Get current user profile |
| `POST` | `/api/auth/logout` | JWT | Revoke session |
| `POST` | `/api/projects` | JWT | Create vlog project (folder_id + concept_prompt) |
| `GET`  | `/api/projects` | JWT | List user's projects (paginated) |
| `GET`  | `/api/projects/:id` | JWT | Project status + summary |
| `GET`  | `/api/projects/:id/files` | JWT | List ingested media files |
| `GET`  | `/api/projects/:id/storyboard` | JWT | Full storyboard with scenes |
| `PUT`  | `/api/projects/:id/storyboard/scenes/:idx` | JWT | Edit scene (transition, pacing, etc.) |
| `GET`  | `/api/projects/:id/references` | JWT | YouTube reference videos |
| `POST` | `/api/projects/:id/generate` | JWT | Approve storyboard → trigger video generation |
| `GET`  | `/api/projects/:id/export` | JWT | Download link for final video |
| `DELETE`| `/api/projects/:id` | JWT | Cancel/delete project and all associated data |

### 1.2 Real-time Endpoints

| Type | Path | Description |
|------|------|-------------|
| SSE | `/api/projects/:id/progress` | Server-Sent Events for pipeline progress |

**SSE Event Format:**

```json
{
  "event": "progress",
  "data": {
    "phase": "INGEST",
    "status": "RUNNING",
    "progress": 0.45,
    "message": "Downloading file 9/20",
    "timestamp": "2026-03-22T10:30:00Z"
  }
}
```

**SSE Implementation:**

```
Client connects → GET /api/projects/:id/progress (Accept: text/event-stream)
  → Backend subscribes to Redis channel: project:{id}:progress
  → Each job worker publishes progress updates to that channel
  → Backend pipes Redis messages → SSE to client
  → Client disconnect → unsubscribe from Redis channel
```

### 1.3 Request Validation (Zod Schemas)

```typescript
import { z } from 'zod'

// POST /api/projects
const CreateProjectSchema = z.object({
  folder_id: z.string().min(1).max(255),
  concept_prompt: z.string().min(10).max(5000),
})

// PUT /api/projects/:id/storyboard/scenes/:idx
const UpdateSceneSchema = z.object({
  description: z.string().min(1).max(1000).optional(),
  mood: z.enum([
    'adventurous', 'romantic', 'peaceful', 'energetic',
    'nostalgic', 'dramatic', 'playful'
  ]).optional(),
  suggested_transition: z.enum([
    'cut', 'cross-dissolve', 'fade-to-black',
    'whip-pan', 'zoom', 'match-cut'
  ]).optional(),
  pacing: z.enum(['slow', 'medium', 'fast']).optional(),
  estimated_duration_seconds: z.number().min(1).max(120).optional(),
})

// Route params
const ProjectIdSchema = z.object({ id: z.string().uuid() })
const SceneIdxSchema = z.object({ idx: z.coerce.number().int().min(0) })

// GET /api/projects (pagination)
const PaginationSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(100).default(20),
})
```

### 1.4 Response Format

All API responses follow a consistent envelope:

```typescript
// Success
{ "ok": true, "data": { ... } }

// Error
{ "ok": false, "error": { "code": "VALIDATION_ERROR", "message": "..." } }

// Paginated
{ "ok": true, "data": [...], "pagination": { "page": 1, "limit": 20, "total": 47 } }
```

---

## 2. Data Ingestion Pipeline

### 2.1 OAuth2 Flow

```
[Frontend] User clicks "Connect Google Drive"
  → Redirect to: https://accounts.google.com/o/oauth2/v2/auth
      ?client_id=${GOOGLE_CLIENT_ID}
      &redirect_uri=${GOOGLE_REDIRECT_URI}
      &response_type=code
      &scope=https://www.googleapis.com/auth/drive.readonly
             https://www.googleapis.com/auth/userinfo.email
             https://www.googleapis.com/auth/userinfo.profile
      &access_type=offline
      &prompt=consent

[Google] User consents → redirects to callback with auth code

[POST /api/auth/google/callback] { code }
  → Exchange code for tokens via Google OAuth2 token endpoint
  → Encrypt tokens (AES-256-GCM) using GCP KMS-managed key
  → Upsert user record with encrypted tokens
  → Issue JWT session token (HS256, 24h expiry)
  → Set JWT in httpOnly + Secure + SameSite=Strict cookie (NOT in response body)
  → Return: { user: { id, email, display_name } }

  NOTE: JWT is NEVER returned in the response body or exposed to JavaScript.
  The frontend reads auth state from GET /api/auth/me (cookie sent automatically).
  This aligns with the front-engineer's security model.
```

**OAuth2 Scopes (minimum necessary):**

| Scope | Justification |
|-------|---------------|
| `drive.readonly` | Read files/folders — no write access needed |
| `userinfo.email` | User identification |
| `userinfo.profile` | Display name in UI |

### 2.2 File Enumeration & Download

```
[INGEST Worker receives job: { projectId }]

Step 1: Enumerate files
  → Decrypt user's OAuth tokens
  → Auto-refresh if token_expires_at < now + 5min
  → GET drive/v3/files?q='${folderId}'+in+parents+and+trashed=false
    &fields=files(id,name,mimeType,size,createdTime,imageMediaMetadata,videoMediaMetadata)
    &pageSize=100&orderBy=createdTime
  → Paginate until nextPageToken is null
  → Filter by supported MIME types
  → Insert media_files rows (metadata_extracted = false)

Step 2: Download files (3 concurrent streams max)
  → For each media_file:
      → Stream from Google Drive → GCP Cloud Storage
      → Path: gs://{bucket}/projects/{projectId}/raw/{fileId}.{ext}
      → Update media_files.gcs_path on completion
      → Publish progress: { phase: 'INGEST', progress: i/total }

Step 3: Extract metadata
  → For each downloaded file:
      → Call Python metadata-extractor microservice (HTTP)
      → Update media_files with EXIF/XMP data
      → Batch reverse-geocode GPS coords → location_name
      → Set metadata_extracted = true
```

**Supported Formats:**

| Format | MIME Type | Max Size |
|--------|-----------|----------|
| JPEG | image/jpeg | 50MB |
| PNG | image/png | 50MB |
| HEIC | image/heic | 50MB |
| MP4 | video/mp4 | 500MB |
| MOV | video/quicktime | 500MB |

**Total project limit:** 5GB (configurable via `MAX_PROJECT_SIZE_BYTES` env var).

### 2.3 Metadata Extraction (Python Microservice)

```python
# Service: metadata-extractor
# Endpoint: POST /extract
# Libraries: exifread, python-xmp-toolkit, ffprobe-python, Pillow

from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)  # Immutable
class MediaMetadata:
    gps_lat: Optional[float]
    gps_lng: Optional[float]
    captured_at: Optional[str]  # ISO 8601
    camera_info: Optional[str]
    orientation: Optional[int]
    duration_ms: Optional[int]
    width: Optional[int]
    height: Optional[int]
    fps: Optional[float]
    codec: Optional[str]

def extract_metadata(file_path: str, mime_type: str) -> MediaMetadata:
    """Extract metadata from media file. Returns immutable dataclass."""
    if mime_type.startswith('image/'):
        exif = _extract_exif(file_path)
        xmp = _extract_xmp(file_path)
        return MediaMetadata(
            gps_lat=exif.get('gps_lat'),
            gps_lng=exif.get('gps_lng'),
            captured_at=exif.get('datetime_original'),
            camera_info=f"{exif.get('make', '')} {exif.get('model', '')}".strip() or None,
            orientation=exif.get('orientation'),
            duration_ms=None,
            width=exif.get('width'),
            height=exif.get('height'),
            fps=None,
            codec=None,
        )
    elif mime_type.startswith('video/'):
        probe = _extract_ffprobe(file_path)
        return MediaMetadata(
            gps_lat=probe.get('gps_lat'),
            gps_lng=probe.get('gps_lng'),
            captured_at=probe.get('creation_time'),
            camera_info=probe.get('camera_info'),
            orientation=probe.get('rotation'),
            duration_ms=probe.get('duration_ms'),
            width=probe.get('width'),
            height=probe.get('height'),
            fps=probe.get('fps'),
            codec=probe.get('codec'),
        )
    return MediaMetadata(*(None,) * 10)
```

---

## 3. Database Schema

### 3.1 Complete ERD

```
users (1) ──→ (N) projects (1) ──→ (N) media_files
                    │                       │
                    │ (1)──→(N)             │
                    ├── generation_jobs      │
                    │                       │
                    ├── storyboard_scenes ←──┘ (via scene_media_files)
                    │         │
                    │         └──→ scene_references ──→ youtube_references
                    │
                    └── youtube_references
```

### 3.2 Table Definitions

#### users

```sql
CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               VARCHAR(255) UNIQUE NOT NULL,
    display_name        VARCHAR(255),
    google_id           VARCHAR(255) UNIQUE NOT NULL,
    access_token_enc    BYTEA NOT NULL,
    refresh_token_enc   BYTEA NOT NULL,
    token_expires_at    TIMESTAMPTZ NOT NULL,
    encryption_key_id   VARCHAR(64) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_google_id ON users(google_id);
```

#### projects

```sql
CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    folder_id       VARCHAR(255) NOT NULL,
    concept_prompt  TEXT NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'CREATED'
                    CHECK (status IN (
                        'CREATED', 'INGESTING', 'ANALYZING', 'PLANNING',
                        'REFERENCING', 'AWAITING_APPROVAL', 'GENERATING',
                        'AUDIO_SYNC', 'EXPORTING', 'COMPLETED', 'FAILED'
                    )),
    total_files     INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    final_video_gcs VARCHAR(1024),
    final_video_duration_ms INTEGER,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_projects_status ON projects(status);
```

#### media_files

```sql
CREATE TABLE media_files (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    drive_file_id       VARCHAR(255) NOT NULL,
    file_name           VARCHAR(512) NOT NULL,
    mime_type           VARCHAR(64) NOT NULL,
    file_size_bytes     BIGINT NOT NULL,
    gcs_path            VARCHAR(1024),
    gps_lat             DOUBLE PRECISION,
    gps_lng             DOUBLE PRECISION,
    location_name       VARCHAR(512),
    captured_at         TIMESTAMPTZ,
    camera_info         VARCHAR(255),
    orientation         SMALLINT,
    duration_ms         INTEGER,
    width               INTEGER,
    height              INTEGER,
    fps                 REAL,
    codec               VARCHAR(32),
    skip_reason         VARCHAR(255),
    metadata_extracted  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_media_files_project_id ON media_files(project_id);
CREATE INDEX idx_media_files_captured_at ON media_files(project_id, captured_at);
```

#### storyboard_scenes

```sql
CREATE TABLE storyboard_scenes (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scene_index             INTEGER NOT NULL,
    description             TEXT NOT NULL,
    mood                    VARCHAR(32) NOT NULL,
    suggested_transition    VARCHAR(32) NOT NULL,
    pacing                  VARCHAR(16) NOT NULL,
    estimated_duration_sec  REAL NOT NULL,
    location_name           VARCHAR(512),
    time_of_day             VARCHAR(16),
    gemini_raw_response     JSONB,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(project_id, scene_index)
);

CREATE INDEX idx_storyboard_scenes_project ON storyboard_scenes(project_id);
```

#### scene_media_files (junction)

```sql
CREATE TABLE scene_media_files (
    scene_id        UUID NOT NULL REFERENCES storyboard_scenes(id) ON DELETE CASCADE,
    media_file_id   UUID NOT NULL REFERENCES media_files(id) ON DELETE CASCADE,
    display_order   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (scene_id, media_file_id)
);
```

#### youtube_references

```sql
CREATE TABLE youtube_references (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    youtube_video_id    VARCHAR(32) NOT NULL,
    title               VARCHAR(512) NOT NULL,
    channel_name        VARCHAR(255),
    thumbnail_url       VARCHAR(1024),
    duration_seconds    INTEGER,
    view_count          BIGINT,
    search_query        VARCHAR(512) NOT NULL,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_youtube_refs_project ON youtube_references(project_id);
```

#### scene_references (junction)

```sql
CREATE TABLE scene_references (
    scene_id        UUID NOT NULL REFERENCES storyboard_scenes(id) ON DELETE CASCADE,
    reference_id    UUID NOT NULL REFERENCES youtube_references(id) ON DELETE CASCADE,
    relevance_score REAL,
    PRIMARY KEY (scene_id, reference_id)
);
```

#### generation_jobs

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
    progress        REAL DEFAULT 0.0,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_log       TEXT,
    worker_id       VARCHAR(128),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_generation_jobs_project ON generation_jobs(project_id);
CREATE INDEX idx_generation_jobs_status ON generation_jobs(status);
CREATE INDEX idx_generation_jobs_phase_status ON generation_jobs(phase, status);
```

### 3.3 Migration Strategy

Use `node-pg-migrate` or Knex migrations. Each table gets its own migration file, ordered by dependency:

```
001_create_users.sql
002_create_projects.sql
003_create_media_files.sql
004_create_storyboard_scenes.sql
005_create_scene_media_files.sql
006_create_youtube_references.sql
007_create_scene_references.sql
008_create_generation_jobs.sql
```

---

## 4. Async Job Architecture

### 4.1 BullMQ Pipeline Overview

```
INGEST → ANALYZE → PLAN → REFERENCE → [user approval] → GENERATE → AUDIO → EXPORT
```

Each phase is a separate BullMQ queue with dedicated workers:

```typescript
import { Queue, Worker } from 'bullmq'

const REDIS_URL = process.env.REDIS_URL
if (!REDIS_URL) throw new Error('REDIS_URL not configured')

const connection = { url: REDIS_URL }

// One queue per phase
const ingestQueue = new Queue('ingest', { connection })
const analyzeQueue = new Queue('analyze', { connection })
const planQueue = new Queue('plan', { connection })
const referenceQueue = new Queue('reference', { connection })
const generateQueue = new Queue('generate', { connection })
const audioQueue = new Queue('audio', { connection })
const exportQueue = new Queue('export', { connection })
```

### 4.2 Job Data Shape

```typescript
interface PipelineJob {
  projectId: string
  phase: 'INGEST' | 'ANALYZE' | 'PLAN' | 'REFERENCE' | 'GENERATE' | 'AUDIO' | 'EXPORT'
  metadata?: Record<string, unknown>  // Phase-specific context
}
```

### 4.3 Worker Pattern (Immutable State Transitions)

```typescript
// Each worker follows this pattern
const ingestWorker = new Worker('ingest', async (job) => {
  const { projectId } = job.data

  // 1. Mark job as RUNNING (DB)
  await updateJobStatus(job.id, 'RUNNING')
  await updateProjectStatus(projectId, 'INGESTING')

  // 2. Execute phase logic
  const result = await executeIngest(projectId, (progress) => {
    // 3. Report progress via Redis pub/sub
    publishProgress(projectId, { phase: 'INGEST', progress })
  })

  // 4. Mark complete, enqueue next phase
  await updateJobStatus(job.id, 'COMPLETED')
  await analyzeQueue.add('analyze', { projectId, phase: 'ANALYZE' })

  return result
}, {
  connection,
  concurrency: 2,  // Max 2 concurrent ingest jobs
})
```

### 4.4 Retry Logic (Exponential Backoff)

```typescript
const defaultJobOptions = {
  attempts: 3,
  backoff: {
    type: 'exponential',
    delay: 2000,  // 2s, 4s, 8s
  },
  removeOnComplete: { age: 86400 },  // Keep completed jobs 24h
  removeOnFail: false,  // Keep failed jobs for inspection
}

// Phase-specific overrides
const phaseRetryConfig = {
  INGEST:    { attempts: 3, backoff: { type: 'exponential', delay: 2000 } },
  ANALYZE:   { attempts: 3, backoff: { type: 'exponential', delay: 2000 } },
  PLAN:      { attempts: 2, backoff: { type: 'exponential', delay: 5000 } },  // Gemini API
  REFERENCE: { attempts: 2, backoff: { type: 'exponential', delay: 5000 } },  // YouTube API
  GENERATE:  { attempts: 2, backoff: { type: 'exponential', delay: 10000 } }, // Veo 3 — expensive
  AUDIO:     { attempts: 3, backoff: { type: 'exponential', delay: 2000 } },
  EXPORT:    { attempts: 3, backoff: { type: 'exponential', delay: 2000 } },
}
```

### 4.5 Dead Letter Queue

```typescript
// Failed jobs after max attempts → DLQ
ingestWorker.on('failed', async (job, error) => {
  if (job.attemptsMade >= job.opts.attempts) {
    // Move to dead letter queue
    await dlqQueue.add(`dlq:${job.data.phase}`, {
      originalJob: job.data,
      error: error.message,
      failedAt: new Date().toISOString(),
      attempts: job.attemptsMade,
    })

    // Update project status to FAILED
    await updateProjectStatus(job.data.projectId, 'FAILED', error.message)

    // Notify user via SSE
    publishProgress(job.data.projectId, {
      phase: job.data.phase,
      status: 'FAILED',
      message: 'Processing failed. Our team has been notified.',
    })
  }
})
```

### 4.6 Progress Reporting (Redis Pub/Sub → SSE)

```typescript
import Redis from 'ioredis'

const redisPub = new Redis(process.env.REDIS_URL)

// Worker publishes progress
function publishProgress(projectId: string, data: ProgressEvent): void {
  redisPub.publish(
    `project:${projectId}:progress`,
    JSON.stringify({ ...data, timestamp: new Date().toISOString() })
  )
}

// --- Shared Subscriber Pattern ---
// One Redis connection fans out to all SSE clients, avoiding per-client connections.
// With 100 concurrent users, this uses 1 Redis subscription connection (not 100).

type SSEClient = { projectId: string; res: Response }

class SSEBroadcaster {
  private sub: Redis
  private clients: Map<string, Set<SSEClient>> = new Map()

  constructor(redisUrl: string) {
    this.sub = new Redis(redisUrl)
    this.sub.on('message', (channel, message) => {
      // channel format: project:{id}:progress
      const projectId = channel.split(':')[1]
      const projectClients = this.clients.get(projectId)
      if (projectClients) {
        for (const client of projectClients) {
          client.res.write(`event: progress\ndata: ${message}\n\n`)
        }
      }
    })
  }

  addClient(client: SSEClient): void {
    const channel = `project:${client.projectId}:progress`
    if (!this.clients.has(client.projectId)) {
      this.clients.set(client.projectId, new Set())
      this.sub.subscribe(channel)
    }
    this.clients.get(client.projectId)!.add(client)
  }

  removeClient(client: SSEClient): void {
    const channel = `project:${client.projectId}:progress`
    const projectClients = this.clients.get(client.projectId)
    if (projectClients) {
      projectClients.delete(client)
      if (projectClients.size === 0) {
        this.clients.delete(client.projectId)
        this.sub.unsubscribe(channel)
      }
    }
  }
}

const sseBroadcaster = new SSEBroadcaster(requireEnv('REDIS_URL'))

// SSE endpoint — uses shared subscriber, no per-client Redis connection
app.get('/api/projects/:id/progress', async (req, res) => {
  const { id } = ProjectIdSchema.parse(req.params)

  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection', 'keep-alive')

  const client: SSEClient = { projectId: id, res }
  sseBroadcaster.addClient(client)

  req.on('close', () => {
    sseBroadcaster.removeClient(client)
  })
})
```

### 4.7 Concurrency Limits

| Queue | Max Concurrency | Rationale |
|-------|----------------|-----------|
| ingest | 2 | Google Drive API rate limits |
| analyze | 4 | CPU-bound metadata extraction |
| plan | 2 | Gemini API rate limits |
| reference | 1 | YouTube API daily quota (10k units) |
| generate | 1 | Veo 3 is expensive, serialize |
| audio | 2 | FFmpeg CPU usage |
| export | 2 | FFmpeg final render |

### 4.8 Redis High Availability & Persistence

**Problem:** Redis is a single point of failure for both job queues (BullMQ) and real-time progress (pub/sub). A Redis crash mid-pipeline silently loses all queued jobs — including expensive GENERATE jobs that took 30+ minutes of Veo 3 processing to reach.

**Production Redis Configuration (GCP Memorystore for Redis):**

| Setting | Value | Rationale |
|---------|-------|-----------|
| Tier | Standard (HA) | Automatic failover with replica |
| Persistence | AOF (appendonly yes, everysec) | Lose at most 1 second of writes on crash |
| RDB snapshots | Every 15 min | Backup for disaster recovery |
| Max memory policy | `noeviction` | BullMQ jobs must never be silently evicted |
| Replica count | 1 (Standard tier) | Automatic failover within ~30s |

**Why Memorystore Standard tier:** Provides automatic replication and failover without managing Sentinel ourselves. If the primary crashes, the replica promotes automatically and BullMQ reconnects.

**Defense in depth — Job recovery from PostgreSQL:**

Even with Redis HA, we treat PostgreSQL `generation_jobs` table as the source of truth:

```typescript
// Startup recovery: find jobs marked RUNNING in DB but missing from Redis queues
async function recoverOrphanedJobs(): Promise<void> {
  const orphaned = await db.query(`
    SELECT id, project_id, phase FROM generation_jobs
    WHERE status = 'RUNNING'
    AND started_at < NOW() - INTERVAL '10 minutes'
  `)

  for (const job of orphaned.rows) {
    // Re-enqueue to the appropriate BullMQ queue
    const queue = getQueueForPhase(job.phase)
    await queue.add(job.phase, {
      projectId: job.project_id,
      phase: job.phase,
      recovered: true,
    })
    await db.query(
      `UPDATE generation_jobs SET status = 'RETRYING', attempt_count = attempt_count + 1 WHERE id = $1`,
      [job.id]
    )
  }
}

// Run on every worker startup
recoverOrphanedJobs()
```

This ensures that even if Redis loses state entirely, no job is permanently lost — the DB-recorded RUNNING state triggers re-enqueue on next startup.

---

## 5. Temporal Pacing Logic

### 5.1 Design Principle

All timing calculations MUST use Python scripts — never mental math or hardcoded values.

### 5.2 Cut Point Calculator

```python
#!/usr/bin/env python3
"""
temporal_pacing.py — Calculate cut points, cross-dissolve timing, and total duration.
Called by the AUDIO phase worker via subprocess.

Usage: python3 temporal_pacing.py --scenes scenes.json --bpm 120 --target-duration 180
"""

import json
import argparse
import sys
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class CutPoint:
    scene_index: int
    start_ms: int
    end_ms: int
    transition_type: str
    transition_duration_ms: int

@dataclass(frozen=True)
class PacingResult:
    total_duration_ms: int
    cuts: List[CutPoint]
    bpm: int
    beat_interval_ms: float

def calculate_beat_interval_ms(bpm: int) -> float:
    """One beat duration in milliseconds."""
    return 60_000.0 / bpm

def calculate_cross_dissolve_ms(transition_type: str, beat_interval_ms: float) -> int:
    """Cross-dissolve duration snapped to beat intervals.

    Formula:
      - 'cut': 0ms (hard cut)
      - 'cross-dissolve': 1 beat duration
      - 'fade-to-black': 2 beat durations
      - 'whip-pan': 0.5 beat duration
      - 'zoom': 1 beat duration
      - 'match-cut': 0.25 beat duration
    """
    multipliers = {
        'cut': 0.0,
        'cross-dissolve': 1.0,
        'fade-to-black': 2.0,
        'whip-pan': 0.5,
        'zoom': 1.0,
        'match-cut': 0.25,
    }
    multiplier = multipliers.get(transition_type, 1.0)
    return int(beat_interval_ms * multiplier)

def calculate_scene_duration_ms(
    estimated_seconds: float,
    pacing: str,
    beat_interval_ms: float,
) -> int:
    """Snap scene duration to nearest beat boundary.

    Pacing multipliers:
      - slow: 1.3x estimated
      - medium: 1.0x estimated
      - fast: 0.7x estimated
    Then round to nearest beat.
    """
    pacing_multipliers = {
        'slow': 1.3,
        'medium': 1.0,
        'fast': 0.7,
    }
    base_ms = estimated_seconds * 1000.0 * pacing_multipliers.get(pacing, 1.0)
    # Snap to nearest beat
    beats = round(base_ms / beat_interval_ms)
    beats = max(beats, 1)  # At least 1 beat
    return int(beats * beat_interval_ms)

def calculate_pacing(scenes: list, bpm: int, target_duration_s: int) -> PacingResult:
    """Main calculation: distribute scenes across target duration, snapped to beats."""
    beat_interval = calculate_beat_interval_ms(bpm)

    # First pass: calculate raw durations
    raw_cuts = []
    current_ms = 0

    for scene in scenes:
        scene_duration = calculate_scene_duration_ms(
            scene['estimated_duration_seconds'],
            scene['pacing'],
            beat_interval,
        )
        transition_duration = calculate_cross_dissolve_ms(
            scene['suggested_transition'],
            beat_interval,
        )

        raw_cuts.append(CutPoint(
            scene_index=scene['scene_index'],
            start_ms=current_ms,
            end_ms=current_ms + scene_duration,
            transition_type=scene['suggested_transition'],
            transition_duration_ms=transition_duration,
        ))

        # Next scene starts after this one, minus transition overlap
        current_ms += scene_duration - transition_duration

    raw_total = current_ms + (raw_cuts[-1].transition_duration_ms if raw_cuts else 0)

    # Second pass: scale to target duration
    target_ms = target_duration_s * 1000
    scale_factor = target_ms / raw_total if raw_total > 0 else 1.0

    scaled_cuts = []
    current_ms = 0

    for cut in raw_cuts:
        duration = int((cut.end_ms - cut.start_ms) * scale_factor)
        # Re-snap to beat
        beats = max(round(duration / beat_interval), 1)
        duration = int(beats * beat_interval)

        transition_duration = calculate_cross_dissolve_ms(
            cut.transition_type, beat_interval
        )

        scaled_cuts.append(CutPoint(
            scene_index=cut.scene_index,
            start_ms=current_ms,
            end_ms=current_ms + duration,
            transition_type=cut.transition_type,
            transition_duration_ms=transition_duration,
        ))

        current_ms += duration - transition_duration

    total_ms = current_ms + (scaled_cuts[-1].transition_duration_ms if scaled_cuts else 0)

    return PacingResult(
        total_duration_ms=total_ms,
        cuts=scaled_cuts,
        bpm=bpm,
        beat_interval_ms=beat_interval,
    )

def main():
    parser = argparse.ArgumentParser(description='Calculate temporal pacing for vlog')
    parser.add_argument('--scenes', required=True, help='Path to scenes JSON file')
    parser.add_argument('--bpm', type=int, required=True, help='BGM beats per minute')
    parser.add_argument('--target-duration', type=int, required=True, help='Target duration in seconds')

    args = parser.parse_args()

    with open(args.scenes) as f:
        scenes = json.load(f)

    result = calculate_pacing(scenes, args.bpm, args.target_duration)

    output = {
        'total_duration_ms': result.total_duration_ms,
        'bpm': result.bpm,
        'beat_interval_ms': result.beat_interval_ms,
        'cuts': [
            {
                'scene_index': c.scene_index,
                'start_ms': c.start_ms,
                'end_ms': c.end_ms,
                'transition_type': c.transition_type,
                'transition_duration_ms': c.transition_duration_ms,
            }
            for c in result.cuts
        ],
    }

    json.dump(output, sys.stdout, indent=2)

if __name__ == '__main__':
    main()
```

### 5.3 Node.js Integration

```typescript
import { execFile } from 'child_process'
import { promisify } from 'util'
import { writeFile, unlink } from 'fs/promises'
import { randomUUID } from 'crypto'

const execFileAsync = promisify(execFile)

async function calculatePacing(
  scenes: StoryboardScene[],
  bpm: number,
  targetDurationSeconds: number,
): Promise<PacingResult> {
  const tmpFile = `/tmp/scenes-${randomUUID()}.json`

  try {
    await writeFile(tmpFile, JSON.stringify(scenes))

    const { stdout } = await execFileAsync('python3', [
      'scripts/temporal_pacing.py',
      '--scenes', tmpFile,
      '--bpm', String(bpm),
      '--target-duration', String(targetDurationSeconds),
    ], { timeout: 30000 })

    return JSON.parse(stdout)
  } finally {
    await unlink(tmpFile).catch(() => {})
  }
}
```

---

## 6. Security

### 6.1 Environment Variables (Required)

All secrets via `process.env` — throw immediately if unset:

```typescript
function requireEnv(name: string): string {
  const value = process.env[name]
  if (!value) {
    throw new Error(`Required environment variable ${name} is not set`)
  }
  return value
}

// Application startup
const config = Object.freeze({
  // Google OAuth2
  GOOGLE_CLIENT_ID: requireEnv('GOOGLE_CLIENT_ID'),
  GOOGLE_CLIENT_SECRET: requireEnv('GOOGLE_CLIENT_SECRET'),
  GOOGLE_REDIRECT_URI: requireEnv('GOOGLE_REDIRECT_URI'),

  // AI APIs
  GEMINI_API_KEY: requireEnv('GEMINI_API_KEY'),
  VEO3_API_KEY: requireEnv('VEO3_API_KEY'),

  // YouTube
  YOUTUBE_API_KEY: requireEnv('YOUTUBE_API_KEY'),

  // Infrastructure
  DATABASE_URL: requireEnv('DATABASE_URL'),
  REDIS_URL: requireEnv('REDIS_URL'),
  GCS_BUCKET: requireEnv('GCS_BUCKET'),

  // Security
  JWT_SECRET: requireEnv('JWT_SECRET'),
  ENCRYPTION_KEY_ID: requireEnv('ENCRYPTION_KEY_ID'),

  // Optional with defaults
  PORT: parseInt(process.env.PORT || '3000', 10),
  MAX_PROJECT_SIZE_BYTES: parseInt(process.env.MAX_PROJECT_SIZE_BYTES || String(5 * 1024 ** 3), 10),
})
```

### 6.2 OAuth Token Encryption

```typescript
import { createCipheriv, createDecipheriv, randomBytes } from 'crypto'

const ALGORITHM = 'aes-256-gcm'
const IV_LENGTH = 16
const TAG_LENGTH = 16

function encryptToken(plaintext: string, key: Buffer): Buffer {
  const iv = randomBytes(IV_LENGTH)
  const cipher = createCipheriv(ALGORITHM, key, iv)
  const encrypted = Buffer.concat([cipher.update(plaintext, 'utf8'), cipher.final()])
  const tag = cipher.getAuthTag()
  // Format: [IV (16)] [TAG (16)] [CIPHERTEXT (N)]
  return Buffer.concat([iv, tag, encrypted])
}

function decryptToken(data: Buffer, key: Buffer): string {
  const iv = data.subarray(0, IV_LENGTH)
  const tag = data.subarray(IV_LENGTH, IV_LENGTH + TAG_LENGTH)
  const ciphertext = data.subarray(IV_LENGTH + TAG_LENGTH)
  const decipher = createDecipheriv(ALGORITHM, key, iv)
  decipher.setAuthTag(tag)
  return decipher.update(ciphertext) + decipher.final('utf8')
}
```

Encryption keys managed via GCP KMS — `encryption_key_id` in users table references the KMS key version for key rotation.

### 6.3 Rate Limiting

```typescript
import rateLimit from 'express-rate-limit'

// Global: 100 requests per 15 minutes per IP
const globalLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
})

// Project creation: 5 per hour per user
const projectCreationLimiter = rateLimit({
  windowMs: 60 * 60 * 1000,
  max: 5,
  keyGenerator: (req) => req.user.id,
})

// Generation trigger: 3 per hour per user
const generationLimiter = rateLimit({
  windowMs: 60 * 60 * 1000,
  max: 3,
  keyGenerator: (req) => req.user.id,
})
```

### 6.4 Input Validation Strategy

| Layer | Tool | What |
|-------|------|------|
| API route params | Zod | UUID format, pagination bounds |
| Request bodies | Zod | All fields typed and constrained |
| Google Drive folder ID | Regex + API validation | Alphanumeric, confirm folder exists |
| File MIME types | Allowlist | Only supported formats pass |
| SQL queries | Parameterized queries (pg) | Never string concatenation |
| File paths | Sanitize + prefix check | Prevent path traversal |

### 6.5 Security Headers

```typescript
import helmet from 'helmet'

app.use(helmet())
app.use(helmet.contentSecurityPolicy({
  directives: {
    defaultSrc: ["'self'"],
    scriptSrc: ["'self'"],
    styleSrc: ["'self'", "'unsafe-inline'"],
    imgSrc: ["'self'", 'https://i.ytimg.com'],  // YouTube thumbnails
    connectSrc: ["'self'", 'https://accounts.google.com'],
  },
}))
```

### 6.6 Logging Security

```typescript
// NEVER log tokens, keys, or PII
const sanitizeLog = (data: Record<string, unknown>): Record<string, unknown> => {
  const sensitive = ['access_token', 'refresh_token', 'api_key', 'password', 'secret']
  return Object.fromEntries(
    Object.entries(data).map(([k, v]) =>
      sensitive.some(s => k.toLowerCase().includes(s))
        ? [k, '[REDACTED]']
        : [k, v]
    )
  )
}
```

---

## Appendix: System Architecture Diagram

```
┌─────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│   Frontend   │────▶│   Node.js API        │────▶│  PostgreSQL     │
│  (React/Vue) │◀────│   (Express/Fastify)  │◀────│  (persistent)   │
└─────────────┘     └──────────┬───────────┘     └─────────────────┘
      │                        │
      │ SSE                    │ BullMQ jobs
      │                        ▼
      │              ┌──────────────────────┐     ┌─────────────────┐
      └──────────────│   Redis              │     │  GCP Cloud      │
                     │   (queues + pub/sub) │     │  Storage        │
                     └──────────────────────┘     │  (media files)  │
                                                  └────────┬────────┘
                     ┌──────────────────────┐              │
                     │  Python Microservices │◀─────────────┘
                     │  - metadata-extractor │
                     │  - temporal-pacing    │
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │  External APIs        │
                     │  - Google Drive       │
                     │  - Gemini 1.5 Pro     │
                     │  - Veo 3              │
                     │  - YouTube Data v3    │
                     └──────────────────────┘
```

---

## Appendix: Environment Variables Checklist

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_CLIENT_ID` | Yes | OAuth2 client ID |
| `GOOGLE_CLIENT_SECRET` | Yes | OAuth2 client secret |
| `GOOGLE_REDIRECT_URI` | Yes | OAuth2 callback URL |
| `GEMINI_API_KEY` | Yes | Gemini 1.5 Pro API key |
| `VEO3_API_KEY` | Yes | Veo 3 API key |
| `YOUTUBE_API_KEY` | Yes | YouTube Data API v3 key |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `GCS_BUCKET` | Yes | Cloud Storage bucket name |
| `JWT_SECRET` | Yes | JWT signing secret (min 32 chars) |
| `ENCRYPTION_KEY_ID` | Yes | GCP KMS key ID for token encryption |
| `PORT` | No | Server port (default: 3000) |
| `MAX_PROJECT_SIZE_BYTES` | No | Max project size (default: 5GB) |
