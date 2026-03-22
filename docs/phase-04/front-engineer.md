# Phase 04: Encoding & Deploy — Frontend Engineering Perspective

> **Conclusion**: The Phase 04 frontend must deliver a real-time, WebSocket-driven export dashboard that streams FFmpeg encoding progress to users, provides download/share options upon completion, and gracefully handles failures with actionable retry UX.

---

## 1. Export Flow UX Design

### 1.1 Export Trigger

The user initiates export from the Studio screen after reviewing the AI-generated storyboard and preview.

```
[Studio Screen] → [Review Storyboard] → [Click "Export Vlog"] → [Export Modal]
```

**Export Modal** presents:
- **Resolution selector**: 1080p (default), 4K, 720p (mobile-optimized)
- **Format selector**: MP4 (H.264), WebM (VP9)
- **Caption toggle**: Burned-in captions vs. SRT sidecar file
- **BGM volume slider**: 0–100% with preview
- **Export to**: Local download / Google Drive folder / both
- **Estimated duration**: Fetched from backend based on storyboard scene count + resolution

### 1.2 Export Confirmation

Before triggering the backend pipeline:
- Display a summary card: resolution, format, duration estimate, destination
- Show estimated processing time (from backend `/api/v1/export/estimate` endpoint)
- Require explicit "Confirm Export" button press

---

## 2. Real-Time Progress Display

### 2.1 Connection Strategy

**Recommendation: Server-Sent Events (SSE) for progress, WebSocket for bidirectional control.**

| Concern | SSE | WebSocket |
|---------|-----|-----------|
| Progress streaming (read-only) | Ideal | Overkill |
| Cancel/pause commands (write) | Not supported | Required |
| Auto-reconnect | Built-in | Manual |
| Proxy-friendly | Yes | Sometimes problematic |

**Hybrid approach**:
- SSE stream on `GET /api/v1/export/{jobId}/progress` for encoding updates
- REST `POST /api/v1/export/{jobId}/cancel` for cancellation (no WebSocket needed for rare writes)

### 2.2 Progress State Model

```typescript
interface ExportProgress {
  readonly jobId: string;
  readonly status: ExportStatus;
  readonly currentStep: ExportStep;
  readonly steps: readonly StepProgress[];
  readonly overallPercent: number;      // 0–100
  readonly estimatedRemaining: number;  // seconds
  readonly errorMessage?: string;
}

type ExportStatus = 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';

type ExportStep =
  | 'analysis'        // Gemini visual analysis
  | 'planning'        // Storyboard generation
  | 'reference'       // YouTube reference fetch
  | 'synthesis'       // Veo 3 video generation
  | 'encoding'        // FFmpeg final encode
  | 'upload';         // Google Drive upload

interface StepProgress {
  readonly step: ExportStep;
  readonly status: 'pending' | 'active' | 'completed' | 'failed';
  readonly percent: number;
  readonly startedAt?: string;         // ISO 8601
  readonly completedAt?: string;       // ISO 8601
}
```

### 2.3 Progress UI Components

#### `<ExportProgressPanel />`
- **Stepper bar**: Horizontal 6-step pipeline indicator (Analysis → Planning → Reference → Synthesis → Encoding → Upload)
- Each step shows: icon, label, status badge, elapsed time
- Active step pulses with animation
- Completed steps show green checkmark + duration

#### `<ExportProgressBar />`
- Overall percentage bar with smooth CSS transitions
- ETA countdown: "~3 min 22 sec remaining"
- Current operation label: "Encoding frame 1,240 / 3,600..."

#### `<ExportLogViewer />` (collapsible)
- Scrollable log stream for power users
- Auto-scrolls to bottom, pause-on-hover
- Filterable by log level: info / warn / error

### 2.4 Reconnection & Resilience

```typescript
// SSE reconnection with exponential backoff
function createProgressStream(jobId: string): EventSource {
  const source = new EventSource(`/api/v1/export/${jobId}/progress`);

  source.onerror = () => {
    // EventSource auto-reconnects with Last-Event-ID
    // UI shows "Reconnecting..." banner after 3s disconnect
  };

  return source;
}
```

- If disconnected > 30 seconds: show "Connection lost" banner with manual retry button
- On reconnect: backend replays current state (not full history) via `Last-Event-ID`
- Progress state is idempotent — duplicate events are safe

---

## 3. Completion & Delivery UX

### 3.1 Success State

When `status === 'completed'`:

```
┌──────────────────────────────────────────────┐
│  ✓ Your vlog is ready!                       │
│                                              │
│  [Video Thumbnail Preview]                   │
│  "Tokyo Spring 2026" · 4:32 · 1080p MP4     │
│                                              │
│  [▶ Play Preview]  [⬇ Download]  [📁 Open   │
│                                  in Drive]   │
│                                              │
│  ── Share ──────────────────────────────────  │
│  [Copy Link]  [Share to Drive]               │
└──────────────────────────────────────────────┘
```

**Actions available**:
- **Play Preview**: In-browser HTML5 video player with full controls
- **Download**: Direct browser download with proper `Content-Disposition` filename
- **Open in Drive**: Deep link to Google Drive file (if uploaded)
- **Copy Link**: Temporary signed URL (24h expiry) for sharing
- **Re-export**: Return to export modal with previous settings pre-filled

### 3.2 Failure State

When `status === 'failed'`:

```typescript
interface ExportError {
  readonly code: ExportErrorCode;
  readonly message: string;           // User-friendly
  readonly retryable: boolean;
  readonly failedStep: ExportStep;
}

type ExportErrorCode =
  | 'ENCODING_TIMEOUT'
  | 'SYNTHESIS_QUOTA_EXCEEDED'
  | 'DRIVE_UPLOAD_FAILED'
  | 'INSUFFICIENT_STORAGE'
  | 'SOURCE_MEDIA_CORRUPTED'
  | 'INTERNAL_ERROR';
```

**Failure UX**:
- Show which step failed (highlighted red in stepper)
- User-friendly error message (never raw stack traces)
- If `retryable`: show "Retry from [failed step]" button
- If not retryable: show "Contact Support" with error code for reference
- All errors logged to console in dev mode only

### 3.3 Cancelled State

- Show "Export cancelled" with option to restart
- Partial artifacts cleaned up by backend (not frontend concern)

---

## 4. Project Dashboard Integration

### 4.1 Export Status in Dashboard

Each project card in the dashboard shows export status:

```typescript
interface ProjectCard {
  readonly id: string;
  readonly title: string;
  readonly thumbnail?: string;
  readonly status: 'draft' | 'processing' | 'ready' | 'failed';
  readonly exportProgress?: number;    // 0–100 when processing
  readonly createdAt: string;
  readonly duration?: number;          // seconds, when ready
}
```

- **Processing**: Mini progress bar on card + "Exporting... 67%"
- **Ready**: Green badge + "Watch" / "Download" quick actions
- **Failed**: Red badge + "Retry" quick action

### 4.2 Background Export Notification

When user navigates away from Studio during export:
- Browser `Notification API` (with permission) fires on completion/failure
- Dashboard auto-refreshes project status via polling (30s interval) or SSE

---

## 5. Performance Considerations

### 5.1 Video Preview

- Use HLS (`.m3u8`) adaptive streaming for preview playback, not raw MP4 download
- Lazy-load video player component (`React.lazy`)
- Poster image (thumbnail) shown before player loads

### 5.2 Download Handling

- Large files (>500MB): Use streaming download with `ReadableStream` + progress indicator
- Provide "Save to Drive" as alternative to browser download for large files
- Never hold full video blob in browser memory

### 5.3 Bundle Impact

- Export-related components loaded only on `/studio/:id/export` route
- SSE/progress utilities: ~2KB gzipped (no heavy dependencies)
- Video player (e.g., `video.js` or native `<video>`): lazy-loaded

---

## 6. Accessibility (WCAG 2.1 AA)

- Progress bar: `role="progressbar"` with `aria-valuenow`, `aria-valuemin`, `aria-valuemax`
- Step status changes announced via `aria-live="polite"` region
- Export completion: focus moves to result card with screen reader announcement
- All interactive elements keyboard-navigable (Tab, Enter, Escape for modal)
- Color-independent status indicators (icons + text labels, not color alone)

---

## 7. Required Backend Endpoints (Phase 04)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/export` | Initiate export job |
| GET | `/api/v1/export/{jobId}/progress` | SSE progress stream |
| POST | `/api/v1/export/{jobId}/cancel` | Cancel export |
| GET | `/api/v1/export/{jobId}/result` | Get completed export metadata + URLs |
| POST | `/api/v1/export/estimate` | Estimate processing time |
| GET | `/api/v1/export/{jobId}/download` | Stream file download |
