# Phase 03: Synthesis & Audio — DevOps/QA Perspective

> **Conclusion**: Phase 03 requires GPU-capable Cloud Run Jobs for FFmpeg synthesis, a 5-stage pipeline with per-stage checkpointing, and Cloud Storage as the intermediary between AI-generated assets and final assembly.

---

## 1. FFmpeg Synthesis Infrastructure

### Cloud Run Jobs for Video Processing

Cloud Run **Jobs** (not Services) are the correct choice for FFmpeg batch processing because:
- Jobs support up to 3600s timeout (vs. 300s for Services HTTP requests)
- Jobs can be allocated up to 8 vCPU + 32 GiB memory
- Jobs don't require an HTTP listener — ideal for batch media processing
- Jobs support task parallelism (multiple tasks per job execution)

```yaml
# cloud-run-job-config.yaml
apiVersion: run.googleapis.com/v1
kind: Job
metadata:
  name: ffmpeg-synthesis
spec:
  template:
    spec:
      containers:
        - image: gcr.io/PROJECT_ID/ffmpeg-worker:latest
          resources:
            limits:
              cpu: "8"
              memory: "32Gi"
          env:
            - name: GCS_INPUT_BUCKET
              value: tripvlog-intermediate-renders
            - name: GCS_OUTPUT_BUCKET
              value: tripvlog-final-output
      timeoutSeconds: 3600
      taskCount: 1
      maxRetries: 2
```

### Container Image: FFmpeg Worker

```dockerfile
# Dockerfile.ffmpeg-worker
FROM linuxserver/ffmpeg:latest AS ffmpeg-base

# Install Python for temporal calculation scripts
RUN apt-get update && apt-get install -y python3 python3-pip && \
    pip3 install google-cloud-storage google-cloud-pubsub

WORKDIR /app
COPY synthesis/ ./synthesis/
COPY scripts/ ./scripts/

ENTRYPOINT ["python3", "synthesis/pipeline_runner.py"]
```

---

## 2. Five-Stage FFmpeg Pipeline

Each stage reads from and writes to GCS, enabling retry at any individual stage.

| Stage | Input | Output | FFmpeg Command Pattern | Estimated Duration (10min vlog) |
|-------|-------|--------|----------------------|-------------------------------|
| 1. Transcode | Raw media (mixed formats) | Normalized H.264 1080p 24fps | `ffmpeg -i input -vf scale=1920:1080 -r 24 -c:v libx264 -preset medium` | 2-5 min |
| 2. Cross-dissolve | Normalized clips + storyboard JSON | Scene-stitched video | `ffmpeg -filter_complex xfade=transition=fade:duration=1:offset=N` | 3-8 min |
| 3. Caption overlay | Stitched video + caption SRT | Captioned video | `ffmpeg -i video -vf subtitles=captions.srt` | 1-2 min |
| 4. BGM mix | Captioned video + BGM audio | Mixed audio/video | `ffmpeg -i video -i bgm -filter_complex amerge,loudnorm` | 1-3 min |
| 5. Final export | Mixed video | H.264 final (target 8Mbps) | `ffmpeg -c:v libx264 -b:v 8M -c:a aac -b:a 192k` | 2-4 min |

### Stage Checkpointing Strategy

```
GCS Bucket: tripvlog-intermediate-renders/
├── {job_id}/
│   ├── stage-1-transcode/       # Normalized clips
│   ├── stage-2-stitched/        # Cross-dissolved video
│   ├── stage-3-captioned/       # With subtitle overlay
│   ├── stage-4-mixed/           # With BGM audio
│   └── stage-5-final/           # Export-ready
```

If any stage fails:
1. Log the FFmpeg stderr output to Cloud Logging
2. Publish failure event to Pub/Sub topic `ffmpeg-stage-failure`
3. Retry the failed stage up to 2 times with exponential backoff
4. If all retries exhausted → mark job as `FAILED`, notify user via API callback

### Temporal Calculation Scripts

Per project rules, all duration/timing math MUST use Python scripts — never LLM mental math:

```python
# scripts/calculate_xfade_offsets.py
"""Calculate cross-dissolve offsets for FFmpeg xfade filter."""
from datetime import timedelta
import json, subprocess, sys

def get_duration(filepath: str) -> float:
    """Get video duration via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", filepath],
        capture_output=True, text=True
    )
    return float(json.loads(result.stdout)["format"]["duration"])

def calculate_offsets(durations: list[float], fade_duration: float = 1.0) -> list[float]:
    """Calculate xfade offset for each transition."""
    offsets = []
    cumulative = 0.0
    for i, dur in enumerate(durations[:-1]):
        cumulative += dur - fade_duration
        offsets.append(round(cumulative, 3))
    return offsets
```

---

## 3. Cloud Storage Architecture

```
GCS Buckets:
├── tripvlog-input-staging/          # Raw uploads from Google Drive sync
│   └── Lifecycle: delete after 7 days
├── tripvlog-intermediate-renders/   # Per-stage FFmpeg outputs
│   └── Lifecycle: delete after 3 days
├── tripvlog-final-output/           # Completed vlogs
│   └── Lifecycle: move to Nearline after 30 days
└── tripvlog-ai-assets/              # Veo 3 generated clips, Gemini outputs
    └── Lifecycle: delete after 7 days
```

### Bucket Policies

- All buckets: uniform bucket-level access (no ACLs)
- `tripvlog-final-output`: signed URLs for user download (expiry: 24h)
- Cross-bucket access via service account with minimal IAM roles:
  - `roles/storage.objectViewer` on input buckets
  - `roles/storage.objectCreator` on output buckets

---

## 4. Testing Requirements for Phase 03

| Test Type | Target | Coverage Goal |
|-----------|--------|---------------|
| Unit (pytest) | `calculate_xfade_offsets`, `get_duration`, volume normalization math | 90% |
| Integration | FFmpeg stage execution with sample 10s clips | 80% |
| Contract | Storyboard JSON schema validation (input to Stage 2) | 100% of fields |
| Smoke | Full 5-stage pipeline with a 30s test video | Pass/Fail gate |

### Sample Test

```python
# tests/test_xfade_offsets.py
def test_calculate_offsets_three_clips():
    durations = [5.0, 3.0, 4.0]
    offsets = calculate_offsets(durations, fade_duration=1.0)
    assert offsets == [4.0, 6.0]  # 5-1=4, 4+(3-1)=6

def test_calculate_offsets_single_clip():
    durations = [10.0]
    offsets = calculate_offsets(durations, fade_duration=1.0)
    assert offsets == []  # No transitions needed
```

---

## 5. Monitoring for Synthesis Phase

### Key Metrics

| Metric | Source | Alert Threshold |
|--------|--------|----------------|
| Stage duration | Cloud Logging (structured) | >15 min for any single stage |
| FFmpeg exit code | Job task exit status | Any non-zero exit |
| GCS intermediate size | Cloud Monitoring | >10 GB per job (cost alert) |
| Job queue depth | Pub/Sub subscription backlog | >20 pending jobs |
| Memory usage | Cloud Run metrics | >90% of allocated |

### Structured Logging Format

```json
{
  "severity": "INFO",
  "job_id": "vlog-abc123",
  "stage": 2,
  "stage_name": "cross-dissolve",
  "status": "completed",
  "duration_seconds": 245.3,
  "input_file_count": 12,
  "output_size_bytes": 524288000
}
```
