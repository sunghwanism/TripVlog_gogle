# Phase 03: Synthesis & Audio — AI Engineer Perspective

> **Conclusion**: Phase 03 executes video synthesis via Veo 3, aligns cuts to musical beats using Python-calculated temporal math, generates audio-synced captions, and produces rendered scene clips ready for final encoding.

---

## 1. Veo 3 Video Synthesis Pipeline

### 1.1 Architecture

```
Refined Storyboard JSON (from Phase 02)
        │
        ▼
  Scene-by-Scene Veo 3 Request Builder
        │
        ▼
  Veo 3 API (per-scene generation)
        │
        ▼
  Scene Clip Validator (resolution, duration, artifacts)
        │
        ▼
  Transition Renderer (cross-dissolve, fade)
        │
        ▼
  Assembly Queue → Phase 04 (FFmpeg encoding)
```

### 1.2 Veo 3 API Request Structure

Each scene is submitted as an independent Veo 3 generation request:

```json
{
  "request_id": "veo3_proj_abc123_scene_001",
  "model": "veo-3",
  "prompt": {
    "text": "Cinematic establishing shot of Osaka castle at golden hour, warm color grading, slow dolly forward, 4K, shallow depth of field, travel vlog aesthetic",
    "reference_images": ["gdrive_url_keyframe_001"],
    "style_parameters": {
      "color_mood": "warm",
      "camera_movement": "dolly-forward",
      "aspect_ratio": "16:9",
      "resolution": "1080p",
      "fps": 30
    }
  },
  "duration_seconds": 4.5,
  "output_format": "mp4",
  "seed": 42
}
```

### 1.3 Prompt Construction per Scene Type

```python
SCENE_PROMPT_TEMPLATES = {
    "establishing": (
        "Cinematic establishing shot of {location_name}, "
        "{color_mood} color grading, slow {camera_move}, "
        "4K quality, {emotion} atmosphere, travel vlog style"
    ),
    "action": (
        "Dynamic {emotion} travel moment at {location_name}, "
        "{color_mood} tones, {camera_move}, "
        "sharp focus, energetic pacing, professional vlog"
    ),
    "transition": (
        "Smooth visual transition, {transition_type} effect, "
        "{color_mood} color palette, {duration}s duration, "
        "seamless flow between scenes"
    ),
    "climax": (
        "Breathtaking cinematic highlight at {location_name}, "
        "{color_mood} grading, dramatic {camera_move}, "
        "peak emotional moment, {emotion} mood, hero shot quality"
    ),
    "outro": (
        "Reflective closing shot, {location_name} at {time_of_day}, "
        "{color_mood} warm fade, gentle {camera_move}, "
        "peaceful {emotion} ending, travel vlog outro"
    ),
}

CAMERA_MOVEMENTS = {
    "establishing": ["dolly-forward", "drone-rise", "slow-pan"],
    "action": ["handheld-follow", "tracking", "whip-pan"],
    "transition": ["static", "slow-tilt"],
    "climax": ["orbit", "crane-up", "reveal"],
    "outro": ["dolly-back", "drone-pullaway", "static-wide"],
}
```

### 1.4 Veo 3 Error Recovery

| Error | Recovery Strategy |
|-------|-------------------|
| Generation timeout (>120s) | Retry with simplified prompt (remove style params) |
| Quality check fail (artifacts) | Re-generate with different seed (+1) |
| Resolution mismatch | Post-process scale via FFmpeg (Phase 04) |
| API rate limit | Queue with exponential backoff, process other scenes first |
| Complete generation failure | Fall back to source clip with color grade filter applied |
| Partial scene (duration mismatch) | Trim/extend via FFmpeg speed adjustment |

**Fallback chain**: Veo 3 → Retry with simpler prompt → Use source clip with filters → Flag for manual review

### 1.5 Scene Validation

Every Veo 3 output is validated before proceeding:

```python
class SceneValidator:
    """Validates Veo 3 generated clips."""

    CHECKS = {
        "duration_tolerance_ms": 500,     # ±500ms from target
        "min_resolution": (1920, 1080),
        "max_file_size_mb": 200,
        "required_codec": "h264",
        "required_fps_range": (29.97, 30.0),
    }

    def validate(self, clip_path: str, expected: SceneSpec) -> ValidationResult:
        """
        1. Probe with ffprobe for metadata
        2. Check duration within tolerance
        3. Verify resolution >= minimum
        4. Check file size bounds
        5. Detect black frames / frozen frames (artifact check)
        Returns: ValidationResult with pass/fail + issues list
        """
```

---

## 2. Cross-Dissolve & Transition Math

> **CRITICAL**: All temporal calculations MUST use Python scripts. Never mental math.

### 2.1 Beat-Aligned Cut Points

```python
# calculate_cut_points.py
"""
Given BPM and scene durations, calculate beat-aligned cut timestamps.

Formula:
  beat_interval_ms = 60_000 / bpm
  For each scene, snap duration to nearest beat boundary.

  snapped_duration = round(original_duration_ms / beat_interval_ms) * beat_interval_ms

  Constraint: snapped_duration must be >= min_duration and <= max_duration
"""

def calculate_cut_points(bpm: float, scenes: list[dict]) -> list[dict]:
    beat_interval_ms = 60_000 / bpm

    cut_points = []
    current_time_ms = 0

    for scene in scenes:
        original_ms = scene["duration_seconds"] * 1000

        # Snap to nearest beat
        beats = round(original_ms / beat_interval_ms)
        beats = max(1, beats)  # minimum 1 beat
        snapped_ms = beats * beat_interval_ms

        # Enforce min/max bounds
        min_ms = scene.get("min_duration_ms", 500)
        max_ms = scene.get("max_duration_ms", 30000)
        snapped_ms = max(min_ms, min(max_ms, snapped_ms))

        cut_points.append({
            "scene_id": scene["scene_id"],
            "start_ms": current_time_ms,
            "end_ms": current_time_ms + snapped_ms,
            "duration_ms": snapped_ms,
            "beats": beats,
        })

        current_time_ms += snapped_ms

    return cut_points
```

### 2.2 Cross-Dissolve Duration Formula

```python
# calculate_crossfade_duration.py
"""
Cross-dissolve duration based on emotional intensity and BPM.

Formula:
  base_duration_ms = 60_000 / bpm  (one beat)

  emotion_multiplier:
    serene/melancholic  → 2.0  (2 beats, slow dissolve)
    joyful/adventurous  → 1.0  (1 beat, standard)
    dramatic            → 1.5  (1.5 beats, dramatic pause)
    energetic           → 0.5  (half beat, quick cut feel)

  crossfade_ms = base_duration_ms * emotion_multiplier
  crossfade_ms = clamp(crossfade_ms, 200, 3000)  # hard bounds
"""

EMOTION_MULTIPLIERS = {
    "serene": 2.0,
    "melancholic": 2.0,
    "joyful": 1.0,
    "adventurous": 1.0,
    "dramatic": 1.5,
    "energetic": 0.5,
    "mysterious": 1.5,
}

def calculate_crossfade(bpm: float, emotion: str) -> int:
    base_ms = 60_000 / bpm
    multiplier = EMOTION_MULTIPLIERS.get(emotion, 1.0)
    crossfade_ms = base_ms * multiplier
    return int(max(200, min(3000, crossfade_ms)))
```

### 2.3 Total Duration Calculation

```python
# calculate_total_duration.py
"""
Sum all scene durations + account for transition overlaps.

For dissolve/fade transitions, the overlap reduces total duration:
  total = sum(scene_durations) - sum(transition_overlaps)

For cuts:
  overlap = 0

For dissolves/fades:
  overlap = transition_duration_ms (scenes overlap during dissolve)
"""

def calculate_total_duration(scenes: list[dict]) -> dict:
    total_scene_ms = sum(s["duration_ms"] for s in scenes)

    total_overlap_ms = 0
    for i in range(len(scenes) - 1):
        if scenes[i]["transition_type"] in ("dissolve", "fade"):
            total_overlap_ms += scenes[i]["transition_duration_ms"]

    total_ms = total_scene_ms - total_overlap_ms

    return {
        "total_duration_ms": total_ms,
        "total_duration_seconds": round(total_ms / 1000, 2),
        "total_scene_duration_ms": total_scene_ms,
        "total_overlap_ms": total_overlap_ms,
        "scene_count": len(scenes),
    }
```

---

## 3. Audio & BGM Pipeline

### 3.1 BGM Selection Logic

Map concept emotions to BPM ranges and musical characteristics:

```python
BGM_PROFILES = {
    "adventurous": {
        "bpm_range": (120, 140),
        "key_preference": ["major"],
        "instruments": ["guitar", "drums", "synth"],
        "energy": "high",
    },
    "serene": {
        "bpm_range": (70, 90),
        "key_preference": ["major", "lydian"],
        "instruments": ["piano", "strings", "ambient"],
        "energy": "low",
    },
    "dramatic": {
        "bpm_range": (90, 110),
        "key_preference": ["minor", "dorian"],
        "instruments": ["orchestra", "percussion", "brass"],
        "energy": "medium-high",
    },
    "joyful": {
        "bpm_range": (110, 130),
        "key_preference": ["major"],
        "instruments": ["ukulele", "claps", "whistling"],
        "energy": "medium-high",
    },
    "energetic": {
        "bpm_range": (130, 160),
        "key_preference": ["major", "mixolydian"],
        "instruments": ["edm-synth", "drums", "bass"],
        "energy": "very-high",
    },
    "melancholic": {
        "bpm_range": (60, 85),
        "key_preference": ["minor", "aeolian"],
        "instruments": ["piano", "cello", "acoustic-guitar"],
        "energy": "low",
    },
    "mysterious": {
        "bpm_range": (80, 100),
        "key_preference": ["minor", "phrygian"],
        "instruments": ["ambient-pad", "strings", "soft-percussion"],
        "energy": "medium-low",
    },
}
```

### 3.2 Audio-Video Beat Sync

```python
# Audio sync algorithm (pseudocode)
"""
Goal: Align video cut points to musical beats.

Steps:
1. Analyze BGM track → extract beat timestamps (using librosa or similar)
2. Get cut points from calculate_cut_points.py
3. For each cut point, find nearest beat timestamp
4. Adjust cut point to align with beat (within tolerance)
5. Recalculate scene durations after alignment

Tolerance: ±50ms from exact beat position
If no beat within tolerance, keep original cut point.
"""

def sync_cuts_to_beats(cut_points: list, beat_timestamps_ms: list) -> list:
    TOLERANCE_MS = 50
    synced = []

    for cut in cut_points:
        # Find nearest beat to this cut's end point
        nearest_beat = min(beat_timestamps_ms, key=lambda b: abs(b - cut["end_ms"]))

        if abs(nearest_beat - cut["end_ms"]) <= TOLERANCE_MS:
            # Snap to beat
            delta = nearest_beat - cut["end_ms"]
            synced.append({
                **cut,
                "end_ms": nearest_beat,
                "duration_ms": cut["duration_ms"] + delta,
                "beat_aligned": True,
            })
        else:
            synced.append({**cut, "beat_aligned": False})

    return synced
```

### 3.3 Audio Ducking for Captions

When captions appear with voiceover potential, BGM volume ducks:

```python
DUCKING_RULES = {
    "caption_present": {
        "bgm_volume_db": -12,       # duck BGM by 12dB
        "fade_in_ms": 200,          # smooth fade in
        "fade_out_ms": 300,         # smooth fade out
    },
    "text_overlay_present": {
        "bgm_volume_db": -6,        # light duck for text overlays
        "fade_in_ms": 100,
        "fade_out_ms": 200,
    },
    "no_overlay": {
        "bgm_volume_db": 0,         # full volume
    },
}
```

---

## 4. Caption Timing Pipeline

### 4.1 Word-Level Timestamps

Use Gemini to generate word-level timing for captions:

```
Prompt to Gemini:
"Given this scene (duration: {duration_ms}ms) and caption text: '{caption_text}',
generate word-level timestamps for smooth caption animation.

Rules:
- Each word should appear at a natural reading pace (~150 WPM)
- First word starts at {start_offset_ms}ms into the scene
- Last word must end at least 500ms before scene ends
- Return JSON array of {word, start_ms, end_ms}"
```

### 4.2 Caption Render Spec

```json
{
  "caption_render_spec": {
    "scene_id": "scene_005",
    "words": [
      { "word": "The", "start_ms": 500, "end_ms": 700 },
      { "word": "journey", "start_ms": 700, "end_ms": 1100 },
      { "word": "begins", "start_ms": 1100, "end_ms": 1500 }
    ],
    "style": {
      "font_family": "Montserrat",
      "font_weight": 600,
      "font_size_px": 48,
      "color": "#FFFFFF",
      "shadow": "2px 2px 4px rgba(0,0,0,0.8)",
      "position": "bottom-center",
      "margin_bottom_px": 80,
      "animation": "fade-word-by-word"
    }
  }
}
```

---

## 5. Phase 03 Output → Phase 04 Handoff

### Assembly Manifest

The complete output of Phase 03 is an **Assembly Manifest** consumed by Phase 04 (FFmpeg encoding):

```json
{
  "project_id": "proj_abc123",
  "assembly_manifest": {
    "version": "1.0",
    "total_duration_ms": 180000,
    "output_spec": {
      "resolution": "1920x1080",
      "fps": 30,
      "codec": "h264",
      "audio_codec": "aac",
      "container": "mp4"
    },
    "timeline": [
      {
        "scene_id": "scene_001",
        "clip_path": "/renders/veo3/scene_001.mp4",
        "start_ms": 0,
        "end_ms": 4500,
        "transition_in": null,
        "transition_out": {
          "type": "dissolve",
          "duration_ms": 800,
          "overlap_with": "scene_002"
        }
      }
    ],
    "audio_tracks": [
      {
        "track_id": "bgm_001",
        "path": "/audio/bgm_adventure_128bpm.mp3",
        "start_ms": 0,
        "end_ms": 180000,
        "volume_keyframes": [
          { "time_ms": 0, "volume_db": -3 },
          { "time_ms": 5000, "volume_db": -12 },
          { "time_ms": 8000, "volume_db": -3 }
        ]
      }
    ],
    "caption_renders": [
      {
        "scene_id": "scene_001",
        "render_spec": "... (caption_render_spec as above)"
      }
    ]
  }
}
```

---

## 6. Dependencies on Other Agents

| Dependency | From | What AI Engineer Needs |
|------------|------|----------------------|
| FFmpeg encoding pipeline | DevOps/QA | Accepts assembly manifest, produces final MP4 |
| BGM library storage | Backend Engineer | Audio file storage + metadata API |
| Scene clip storage | DevOps/QA | Temp storage for Veo 3 rendered clips |
| Caption rendering engine | DevOps/QA | FFmpeg subtitle/text overlay commands |
| Progress tracking | Frontend Engineer | WebSocket updates for Veo 3 generation progress |
