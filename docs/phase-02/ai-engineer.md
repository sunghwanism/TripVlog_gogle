# Phase 02: Narrative & Reference — AI Engineer Perspective

> **Conclusion**: Phase 02 builds the narrative layer — fetching YouTube style references, extracting editing patterns, and transforming the raw storyboard into a cohesive narrative arc aligned with the user's concept prompt.

---

## 1. YouTube Reference Fetching Pipeline

### 1.1 Architecture

```
User Concept Prompt + Storyboard Emotions/Locations
        │
        ▼
  Search Query Constructor
        │
        ▼
  YouTube Data API v3 (search.list + videos.list)
        │
        ▼
  Reference Filter & Ranker
        │
        ▼
  Style Extraction Engine (Gemini)
        │
        ▼
  Reference Style Profile JSON
```

### 1.2 Search Query Construction

Build search queries from three signal sources:

```python
def build_youtube_queries(concept: str, locations: list[str], emotions: list[str]) -> list[str]:
    """
    Generate 3-5 targeted YouTube search queries.

    Strategy:
    - Query 1: Direct concept match → "cinematic {concept} vlog"
    - Query 2: Location-specific → "{primary_location} travel vlog cinematic"
    - Query 3: Style-specific → "{dominant_emotion} travel video edit"
    - Query 4 (optional): Creator-style → "travel vlog {emotion} color grade"
    - Query 5 (optional): Technique → "cinematic b-roll {location} drone"
    """
    queries = []
    queries.append(f"cinematic {concept} vlog")

    if locations:
        queries.append(f"{locations[0]} travel vlog cinematic")

    if emotions:
        emotion_map = {
            "adventurous": "epic adventure",
            "serene": "peaceful calm",
            "dramatic": "dramatic cinematic",
            "joyful": "happy upbeat",
            "energetic": "fast paced dynamic"
        }
        mapped = emotion_map.get(emotions[0], emotions[0])
        queries.append(f"{mapped} travel video edit")

    return queries[:5]  # cap at 5 queries
```

### 1.3 YouTube API Integration

#### API Call: `search.list`

```
GET https://www.googleapis.com/youtube/v3/search
Parameters:
  part: snippet
  q: {constructed_query}
  type: video
  videoDuration: medium          # 4-20 minutes
  order: viewCount
  publishedAfter: {2_years_ago}  # fresh content only
  maxResults: 10
  relevanceLanguage: en
  key: {process.env.YOUTUBE_API_KEY}   # NEVER hardcoded
```

**Cost**: 100 units per search.list call × 5 queries = **500 units per project**

#### API Call: `videos.list` (for selected candidates)

```
GET https://www.googleapis.com/youtube/v3/videos
Parameters:
  part: snippet,contentDetails,statistics
  id: {comma_separated_video_ids}
  key: {process.env.YOUTUBE_API_KEY}
```

**Cost**: 1 unit per videos.list call

### 1.4 YouTube API Quota Management

**Daily quota: 10,000 units**

| Operation | Units | Max Calls/Day |
|-----------|-------|---------------|
| search.list | 100 | 100 |
| videos.list | 1 | 10,000 |
| captions.list | 50 | 200 |

**Budget per project**: 550 units max (5 searches + 50 video details)

**Strategy**:
- Cap at ~18 projects per day on YouTube references
- Cache all results in database (TTL: 7 days)
- Before any API call, check cache first
- Implement daily counter: abort YouTube fetching if > 8,000 units consumed

```python
class YouTubeQuotaTracker:
    """
    Redis-backed quota counter.
    Key: youtube_quota:{date_YYYYMMDD}
    Value: cumulative units consumed
    TTL: 48 hours
    """
    DAILY_LIMIT = 10_000
    SAFETY_THRESHOLD = 8_000  # stop fetching at 80%

    async def can_spend(self, units: int) -> bool:
        current = await self.redis.get(self._today_key())
        return (int(current or 0) + units) < self.SAFETY_THRESHOLD

    async def record(self, units: int) -> None:
        await self.redis.incrby(self._today_key(), units)
        await self.redis.expire(self._today_key(), 48 * 3600)
```

### 1.5 Reference Filtering & Ranking

After retrieving candidates, filter and rank:

```python
FILTER_CRITERIA = {
    "min_view_count": 10_000,
    "min_duration_seconds": 120,   # 2 minutes
    "max_duration_seconds": 480,   # 8 minutes
    "max_age_days": 730,           # 2 years
    "exclude_channels": [],        # blocklist for spam/low-quality
}

RANKING_WEIGHTS = {
    "view_count_normalized": 0.3,      # log-scaled views
    "like_ratio": 0.2,                 # likes / (likes + dislikes estimate)
    "title_relevance": 0.3,            # cosine similarity to concept
    "recency_bonus": 0.2,              # newer = higher score
}
```

Select **top 3 reference videos** per project.

### 1.6 Caching Strategy

```
Cache Layer: Redis + PostgreSQL

Redis (hot cache, TTL: 24h):
  Key: yt_search:{query_hash}
  Value: search results JSON

PostgreSQL (warm cache, TTL: 7 days):
  Table: youtube_references
  Columns: query_hash, video_id, snippet, statistics, fetched_at
  Index: (query_hash, fetched_at DESC)

Cache hit flow:
  1. Check Redis → hit → return
  2. Check PostgreSQL (fetched_at < 7 days) → hit → populate Redis, return
  3. Miss → call YouTube API → store in both Redis + PostgreSQL
```

---

## 2. Style Extraction Engine

### 2.1 Pacing Analysis

Extract editing rhythm from reference videos using their metadata:

```python
class StyleProfile:
    """Extracted from top 3 YouTube references."""
    cuts_per_minute: float        # estimated from duration / typical scene count
    avg_scene_duration_sec: float # target for our storyboard
    transition_preference: str    # "cut-heavy" | "dissolve-heavy" | "mixed"
    color_mood: str               # "warm" | "cool" | "desaturated" | "vibrant"
    pacing_curve: str             # "slow-build" | "constant" | "wave" | "crescendo"
    text_overlay_style: str       # "minimal" | "bold-title" | "subtitle-heavy"
```

### 2.2 Gemini-Based Style Analysis

Send reference video thumbnails + titles to Gemini for style inference:

```
System Prompt:
"You are a video editing style analyst. Given YouTube travel vlog references
(title, description, thumbnail), infer the editing style profile."

User Prompt:
"Analyze these {n} reference travel vlogs and extract a unified style profile:

References:
{for each: title, description, thumbnail_url, view_count, duration}

Return JSON:
{
  "cuts_per_minute": number,
  "avg_scene_duration_sec": number,
  "transition_preference": "cut-heavy" | "dissolve-heavy" | "mixed",
  "color_mood": "warm" | "cool" | "desaturated" | "vibrant",
  "pacing_curve": "slow-build" | "constant" | "wave" | "crescendo",
  "text_overlay_style": "minimal" | "bold-title" | "subtitle-heavy",
  "confidence": number (0-1)
}"
```

---

## 3. Narrative Construction

### 3.1 Storyboard Reordering

After Phase 01 analysis and Phase 02 style extraction, reorder scenes into a narrative arc:

```
Narrative Arc Template:
  1. HOOK (0-5s)         → Most visually striking scene, fast cuts
  2. ESTABLISH (5-15s)   → Location establishing shots, slow pacing
  3. RISING (15-60%)     → Action scenes, building energy
  4. CLIMAX (60-80%)     → Peak moments, longest scenes, most dramatic
  5. RESOLUTION (80-95%) → Winding down, reflective scenes
  6. OUTRO (95-100%)     → Closing montage, fade to black
```

### 3.2 Scene Reordering Algorithm

```
Input: scenes[] from Phase 01 storyboard
Input: style_profile from reference analysis

Algorithm:
1. Sort scenes by capture_time (chronological base order)
2. Identify "hero shots" (quality_score >= 8.0) → reserve for CLIMAX
3. Identify establishing shots (scene_type == "establishing") → place in ESTABLISH
4. Apply narrative arc template:
   a. Pick highest-quality action scene → HOOK
   b. Place establishing scenes → ESTABLISH
   c. Distribute remaining action scenes → RISING (sorted by energy: emotion_tags)
   d. Place hero shots → CLIMAX
   e. Place serene/melancholic scenes → RESOLUTION
   f. Generate outro from remaining footage → OUTRO
5. Apply style_profile.pacing_curve to adjust scene durations
6. Recalculate total_duration_seconds via Python script
```

### 3.3 Gemini Narrative Prompt

After algorithmic reordering, use Gemini for narrative refinement:

```
System Prompt:
"You are a professional travel vlog storyteller. Given a reordered storyboard
and concept prompt, refine the narrative flow."

User Prompt:
"Concept: {concept_prompt}
Style Profile: {style_profile_json}

Current storyboard order:
{scenes_json}

Tasks:
1. Verify the narrative arc feels natural
2. Suggest any scene reordering for better flow
3. Generate captions for each scene that match the concept tone
4. Suggest where text overlays should appear (location titles, dates)
5. Flag any pacing issues (e.g., two slow scenes back-to-back)

Return the refined storyboard JSON with updated order, captions, and annotations."
```

---

## 4. Caption Generation

### 4.1 Caption Schema

```json
{
  "captions": [
    {
      "caption_id": "cap_001",
      "scene_id": "scene_001",
      "text": "The journey begins at dawn",
      "start_ms": 0,
      "end_ms": 3000,
      "style": "cinematic",
      "position": "bottom-center",
      "font_size": "medium",
      "animation": "fade-in",
      "language": "en"
    }
  ],
  "text_overlays": [
    {
      "overlay_id": "ovl_001",
      "scene_id": "scene_003",
      "text": "Osaka, Japan",
      "start_ms": 500,
      "end_ms": 3500,
      "style": "bold-title",
      "position": "center",
      "animation": "slide-up"
    }
  ]
}
```

### 4.2 Caption Styling Rules

| Concept Emotion | Caption Style | Font | Animation |
|----------------|---------------|------|-----------|
| adventurous | bold | Sans-serif heavy | slide-in |
| serene | minimal | Thin serif | fade-in |
| dramatic | cinematic | Condensed caps | reveal |
| joyful | handwritten | Script/handwritten | bounce |
| energetic | bold | Impact/block | flash |

---

## 5. Phase 02 Output

### What Phase 02 Produces

1. **Reference Style Profile** — JSON with editing metrics from YouTube analysis
2. **Refined Storyboard** — Reordered scenes with narrative arc applied
3. **Caption Layer** — Per-scene captions with timing and styling
4. **Text Overlay Layer** — Location titles, date markers

### What Phase 03 Consumes

Phase 03 (Synthesis) receives the complete refined storyboard including:
- Scene order + durations (narrative arc applied)
- Style profile (cuts_per_minute, color_mood, pacing_curve)
- Caption + overlay timing data
- BGM requirements (emotion → BPM range mapping)

---

## 6. Dependencies on Other Agents

| Dependency | From | What AI Engineer Needs |
|------------|------|----------------------|
| YouTube API key management | Backend Engineer | Secure credential injection via env vars |
| Redis cache infrastructure | DevOps/QA | Redis instance for quota tracking + caching |
| Database schema for references | Backend Engineer | `youtube_references` table |
| Storyboard storage update | Backend Engineer | PUT endpoint for refined storyboard |
