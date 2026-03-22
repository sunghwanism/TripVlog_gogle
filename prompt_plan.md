# Phase 01 Implementation Plan — Data & Analysis

> Confirmed: 2026-03-22. PC-only project.

## Project Structure

```
TripVlog_gogle/
├── backend/                          # Node.js/TypeScript API
│   ├── src/
│   │   ├── routes/auth.ts            # OAuth2 callback + /me
│   │   ├── routes/projects.ts        # Project CRUD + SSE
│   │   ├── services/drive.ts         # Google Drive API client
│   │   ├── services/encryption.ts    # AES-256-GCM token encryption
│   │   ├── services/storage.ts       # GCS streaming upload
│   │   ├── workers/ingest.worker.ts  # BullMQ INGEST job
│   │   ├── workers/analyze.worker.ts # BullMQ ANALYZE job
│   │   ├── db/schema.sql             # 4-table PostgreSQL DDL
│   │   ├── db/client.ts              # pg pool setup
│   │   ├── middleware/auth.ts        # JWT cookie verification
│   │   └── validation/schemas.ts     # Zod schemas
│   ├── tests/
│   └── package.json
│
└── ai-service/                       # Python microservice
    ├── src/
    │   ├── extractor/metadata.py     # EXIF/XMP/ffprobe extraction
    │   ├── extractor/geocoding.py    # Reverse geocoding
    │   ├── clustering/gps_cluster.py # DBSCAN-inspired grouping
    │   ├── gemini/analyzer.py        # GeminiAnalyzer class
    │   ├── gemini/prompts.py         # Prompt templates
    │   ├── gemini/validator.py       # Pydantic models
    │   ├── schemas/storyboard.json   # JSON Schema v7
    │   └── api.py                    # FastAPI entry point
    ├── tests/
    └── requirements.txt
```

## Phases

### Backend (A→E)
- A: DB schema + pg client + env.example
- B: AES-256-GCM encryption + OAuth2 routes + JWT middleware
- C: Drive enumeration + GCS streaming download (3 concurrent, exponential backoff)
- D: BullMQ INGEST + ANALYZE workers + SSE via Redis pub/sub
- E: REST endpoints with Zod validation

### AI Service (F→I) — parallel with backend
- F: FastAPI + metadata extractor (exifread, xmp-toolkit, ffprobe) + geocoding
- G: GPS clustering (Haversine + DBSCAN-inspired, eps=500m)
- H: GeminiAnalyzer (batch 10-15 items, prompt injection defense, Pydantic validation)
- I: Storyboard JSON Schema v7 + assembly + quality gate (score < 3.0 exclusion)

### Tests (J) — TDD woven throughout
- Jest for backend (80%+ coverage)
- pytest for AI service (80%+ coverage)
