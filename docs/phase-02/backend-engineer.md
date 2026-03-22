# Phase 02: Narrative & Reference — Backend Engineer

> **Conclusion:** Phase 02 transforms raw media metadata into a structured storyboard by orchestrating Gemini 1.5 Pro for visual analysis and YouTube Data API for style references. The backend manages the data flow between AI analysis, reference fetching, and storyboard persistence.

---

## 1. Storyboard Data Flow Overview

```
Phase 01 output (media_files with metadata)
  → PLAN job: Gemini 1.5 Pro analyzes clips + concept_prompt → storyboard JSON
  → REFERENCE job: YouTube Data API fetches style reference videos
  → storyboard_scenes table populated with scene order, transitions, references
  → Ready for Phase 03 (Synthesis & Audio)
```

---

## 2. Gemini 1.5 Pro Integration

### 2.1 Visual Analysis Pipeline

The PLAN phase sends media files + metadata to Gemini 1.5 Pro for scene understanding:

```
[PLAN Worker]
  → Load all media_files for project (ordered by captured_at)
  → Group files by location_name + time proximity (< 2 hours gap = same scene)
  → For each scene group:
      → Upload representative frames to Gemini (max 10 per scene)
      → Prompt Gemini with: scene media + concept_prompt + metadata context
      → Receive: scene description, mood, suggested transitions, pacing notes
  → Assemble full storyboard JSON
  → Persist to storyboard_scenes table
```

### 2.2 Gemini API Call Pattern

```typescript
// Environment variable — never hardcoded
const GEMINI_API_KEY = process.env.GEMINI_API_KEY
if (!GEMINI_API_KEY) {
  throw new Error('GEMINI_API_KEY not configured')
}

// Prompt structure for scene analysis
const sceneAnalysisPrompt = {
  system: `You are a professional video editor analyzing trip footage.
    Concept: "${project.concept_prompt}"
    Output a JSON storyboard scene with: description, mood, suggested_transition,
    pacing (slow/medium/fast), estimated_duration_seconds.`,
  contents: [
    // Media thumbnails/frames uploaded as inline data
    ...sceneFrames.map(frame => ({
      inlineData: { mimeType: frame.mimeType, data: frame.base64 }
    })),
    // Metadata context
    {
      text: JSON.stringify({
        location: sceneGroup.location_name,
        time_range: { start: sceneGroup.startTime, end: sceneGroup.endTime },
        file_count: sceneGroup.files.length,
        total_duration_ms: sceneGroup.totalDuration,
      })
    }
  ]
}
```

### 2.3 Storyboard JSON Schema

Gemini outputs validated against a Zod schema before persistence:

```typescript
import { z } from 'zod'

const StoryboardSceneSchema = z.object({
  scene_index: z.number().int().min(0),
  description: z.string().min(1).max(1000),
  mood: z.enum(['adventurous', 'romantic', 'peaceful', 'energetic', 'nostalgic', 'dramatic', 'playful']),
  suggested_transition: z.enum(['cut', 'cross-dissolve', 'fade-to-black', 'whip-pan', 'zoom', 'match-cut']),
  pacing: z.enum(['slow', 'medium', 'fast']),
  estimated_duration_seconds: z.number().min(1).max(120),
  media_file_ids: z.array(z.string().uuid()).min(1),
  location_name: z.string().nullable(),
  time_of_day: z.enum(['morning', 'afternoon', 'evening', 'night']).nullable(),
})

const StoryboardSchema = z.object({
  project_id: z.string().uuid(),
  title: z.string().min(1).max(200),
  total_duration_seconds: z.number().min(10).max(600),
  scenes: z.array(StoryboardSceneSchema).min(1).max(50),
})
```

---

## 3. YouTube Data API Integration

### 3.1 Reference Video Fetching

The REFERENCE phase uses storyboard mood + concept to find style reference videos:

```
[REFERENCE Worker]
  → Read storyboard scenes (mood, pacing, location context)
  → Build search queries per scene mood:
      mood: "adventurous" + location: "Tokyo" → "Tokyo adventure vlog cinematic"
      mood: "peaceful" + location: "Bali"    → "Bali peaceful travel cinematic"
  → YouTube Data API v3 search (max 3 results per query)
  → Store references in youtube_references table
  → Link references to scenes via scene_references junction table
```

### 3.2 YouTube API Call Pattern

```typescript
const YOUTUBE_API_KEY = process.env.YOUTUBE_API_KEY
if (!YOUTUBE_API_KEY) {
  throw new Error('YOUTUBE_API_KEY not configured')
}

// Search for reference videos
// GET https://www.googleapis.com/youtube/v3/search
const searchParams = {
  part: 'snippet',
  q: buildSearchQuery(scene.mood, scene.location_name, project.concept_prompt),
  type: 'video',
  videoCategoryId: '19',  // Travel & Events
  maxResults: 3,
  order: 'relevance',
  videoDefinition: 'high',
  key: YOUTUBE_API_KEY,
}

// Get video details for duration/stats
// GET https://www.googleapis.com/youtube/v3/videos
const videoParams = {
  part: 'contentDetails,statistics,snippet',
  id: videoIds.join(','),
  key: YOUTUBE_API_KEY,
}
```

### 3.3 API Quota Management

YouTube Data API v3 quota: 10,000 units/day.

| Operation | Cost | Estimated per project |
|-----------|------|----------------------|
| search.list | 100 units | ~5 searches = 500 units |
| videos.list | 1 unit | ~15 videos = 15 units |
| **Total per project** | | **~515 units** |

Max ~19 projects/day on default quota. Backend tracks daily usage in Redis:

```
INCR youtube:quota:2026-03-22  // increment per API call cost
EXPIRE youtube:quota:2026-03-22 90000  // TTL ~25 hours
```

If quota approaches 9,000, reject new REFERENCE jobs with retry-after header.

---

## 4. Database Schema (Phase 02 Tables)

### 4.1 storyboard_scenes

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
    gemini_raw_response     JSONB,  -- full Gemini output for audit
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(project_id, scene_index)
);

CREATE INDEX idx_storyboard_scenes_project ON storyboard_scenes(project_id);
```

### 4.2 scene_media_files (junction)

```sql
CREATE TABLE scene_media_files (
    scene_id    UUID NOT NULL REFERENCES storyboard_scenes(id) ON DELETE CASCADE,
    media_file_id UUID NOT NULL REFERENCES media_files(id) ON DELETE CASCADE,
    display_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (scene_id, media_file_id)
);
```

### 4.3 youtube_references

```sql
CREATE TABLE youtube_references (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    youtube_video_id VARCHAR(32) NOT NULL,
    title           VARCHAR(512) NOT NULL,
    channel_name    VARCHAR(255),
    thumbnail_url   VARCHAR(1024),
    duration_seconds INTEGER,
    view_count      BIGINT,
    search_query    VARCHAR(512) NOT NULL,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_youtube_refs_project ON youtube_references(project_id);
```

### 4.4 scene_references (junction)

```sql
CREATE TABLE scene_references (
    scene_id        UUID NOT NULL REFERENCES storyboard_scenes(id) ON DELETE CASCADE,
    reference_id    UUID NOT NULL REFERENCES youtube_references(id) ON DELETE CASCADE,
    relevance_score REAL,  -- 0.0 to 1.0, from Gemini relevance rating
    PRIMARY KEY (scene_id, reference_id)
);
```

---

## 5. Phase 02 API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/api/projects/:id/storyboard` | Get full storyboard with scenes and media assignments |
| `PUT`  | `/api/projects/:id/storyboard/scenes/:idx` | User edits a scene (reorder, change transition, etc.) |
| `GET`  | `/api/projects/:id/references` | List YouTube reference videos for the project |
| `POST` | `/api/projects/:id/generate` | Approve storyboard → trigger Phase 03 GENERATE job |

### Storyboard Edit Validation

```typescript
const UpdateSceneSchema = z.object({
  description: z.string().min(1).max(1000).optional(),
  mood: z.enum(['adventurous', 'romantic', 'peaceful', 'energetic', 'nostalgic', 'dramatic', 'playful']).optional(),
  suggested_transition: z.enum(['cut', 'cross-dissolve', 'fade-to-black', 'whip-pan', 'zoom', 'match-cut']).optional(),
  pacing: z.enum(['slow', 'medium', 'fast']).optional(),
  estimated_duration_seconds: z.number().min(1).max(120).optional(),
})
```

---

## 6. Phase 02 Job Flow

```
[PLAN Worker — triggered after Phase 01 ANALYZE completes]
  → Load project + media_files (with metadata)
  → Group media into scenes by location + time
  → For each scene group:
      → Extract representative frames (first, middle, last)
      → Upload frames to Gemini 1.5 Pro with context
      → Validate response against StoryboardSceneSchema
      → Insert storyboard_scenes + scene_media_files rows
  → Update project.status = 'PLANNING' → 'REFERENCING'
  → Enqueue REFERENCE job

[REFERENCE Worker]
  → Load storyboard_scenes for project
  → For each unique mood+location combination:
      → Query YouTube Data API (search + video details)
      → Insert youtube_references rows
      → Link to scenes via scene_references
  → Update project.status = 'REFERENCING' → 'AWAITING_APPROVAL'
  → Notify frontend via SSE: storyboard ready for review
```

---

## 7. Error Handling

| Error | Strategy |
|-------|----------|
| Gemini API 429 | Exponential backoff: 5s, 10s, 20s, max 3 attempts |
| Gemini invalid JSON response | Re-prompt with stricter format instructions, max 2 retries |
| Gemini response fails Zod validation | Log raw response, retry with explicit field requirements |
| YouTube API quota exceeded | Defer REFERENCE job to next day, notify user via SSE |
| YouTube API 403 (forbidden) | Check API key validity, alert ops, fail job |

---

## 8. Data Immutability Pattern

All storyboard modifications create new versions — no in-place mutation:

```typescript
// Immutable scene update
function updateScene(
  existingScene: StoryboardScene,
  updates: Partial<StoryboardScene>
): StoryboardScene {
  return {
    ...existingScene,
    ...updates,
    updated_at: new Date().toISOString(),
  }
}
```

Original Gemini responses are preserved in `gemini_raw_response` JSONB column for audit trail.
