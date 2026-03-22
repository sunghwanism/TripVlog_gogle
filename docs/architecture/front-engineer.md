# Video Studio — Complete UI/UX Architecture

> **Conclusion**: A React + TypeScript SPA using Zustand for client state, TanStack Query for server state, and SSE for real-time pipeline progress. Google OAuth2 PKCE flow with httpOnly cookie token storage. Atomic design component hierarchy across 5 screens: Auth, Dashboard, Studio, Export, and Settings.

---

## Table of Contents

1. [Application Screens & Routes](#1-application-screens--routes)
2. [Component Architecture](#2-component-architecture)
3. [State Management](#3-state-management)
4. [API Integration Layer](#4-api-integration-layer)
5. [Security: XSS Sanitization Policy](#5-security-xss-sanitization-policy)
6. [Accessibility & Performance](#6-accessibility--performance)

---

## 1. Application Screens & Routes

### 1.1 Route Map

```
/                        → Redirect to /dashboard (if authed) or /auth
/auth                    → Onboarding / Google OAuth
/auth/callback           → OAuth PKCE callback handler
/dashboard               → Project list
/studio/:projectId       → Core workspace
/studio/:projectId/export → Export progress & delivery
/settings                → Preferences & connection management
```

All routes except `/auth` and `/auth/callback` are protected by `<AuthGuard />`.

### 1.2 Screen Specifications

#### Auth Screen (`/auth`)

**Purpose**: Connect Google Drive via OAuth2 PKCE flow.

```
┌─────────────────────────────────────────┐
│           TripVlog Studio               │
│                                         │
│   Transform your travel footage into    │
│   cinematic vlogs with AI              │
│                                         │
│   [🔗 Connect Google Drive]             │
│                                         │
│   By connecting, you grant access to    │
│   a specific folder only.              │
│                                         │
│   Powered by Gemini + Veo 3            │
└─────────────────────────────────────────┘
```

**OAuth2 PKCE Flow**:
1. User clicks "Connect Google Drive"
2. Generate `code_verifier` + `code_challenge` (SHA-256)
3. Redirect to Google OAuth consent screen with:
   - `response_type=code`
   - `code_challenge_method=S256`
   - `scope=https://www.googleapis.com/auth/drive.readonly`
4. Google redirects to `/auth/callback?code=XXX`
5. Frontend sends `code` + `code_verifier` to backend `POST /api/v1/auth/token`
6. Backend exchanges code for tokens, sets `httpOnly` + `Secure` + `SameSite=Strict` cookie
7. Frontend redirects to `/dashboard`

**Security**: Tokens NEVER touch `localStorage`, `sessionStorage`, or JavaScript-accessible cookies. The backend proxies all Google API calls with the stored token.

#### Project Dashboard (`/dashboard`)

**Purpose**: List, create, and manage vlog projects.

```
┌─────────────────────────────────────────────────┐
│  TripVlog Studio          [+ New Project]  [⚙]  │
│─────────────────────────────────────────────────│
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ 🖼 thumb  │  │ 🖼 thumb  │  │ 🖼 thumb  │      │
│  │ Tokyo '26 │  │ Bali Trip│  │ Paris... │      │
│  │ ✓ Ready   │  │ ⏳ 67%   │  │ ✗ Failed │      │
│  │ 4:32      │  │ ███░░    │  │ [Retry]  │      │
│  └──────────┘  └──────────┘  └──────────┘      │
│                                                  │
│  Showing 3 of 12 projects    [Load More]        │
└─────────────────────────────────────────────────┘
```

**Features**:
- Grid layout (responsive: 1–4 columns)
- Status badges: Draft (gray), Processing (blue + progress), Ready (green), Failed (red)
- Sort: newest first (default), alphabetical, status
- Filter: All, Processing, Ready, Failed
- Cursor-based pagination (not offset-based)
- Click card → navigate to `/studio/:projectId`

#### Studio Screen (`/studio/:projectId`)

**Purpose**: Core workspace for prompt input, folder selection, storyboard review, and generation monitoring.

```
┌─────────────────────────────────────────────────────────┐
│  ← Dashboard    "Tokyo Spring 2026"          [Export ▶] │
│─────────────────────────────────────────────────────────│
│                                                          │
│  ┌─ Concept Prompt ──────────────────────────────────┐  │
│  │ Create a cinematic vlog of our Tokyo cherry       │  │
│  │ blossom trip with lo-fi aesthetic...               │  │
│  │                                                    │  │
│  │ Style: [lo-fi] [cinematic] [warm tones] [+ Add]  │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  📁 Source: /My Drive/Tokyo 2026  [Change Folder]       │
│     42 photos, 8 videos (2.3 GB)                        │
│                                                          │
│  ┌─ AI Storyboard ───────────────────────────────────┐  │
│  │                                                    │  │
│  │  [Scene 1]──[Scene 2]──[Scene 3]──[Scene 4]──... │  │
│  │  Arrival    Shibuya    Sakura     Tsukiji         │  │
│  │  0:00-0:32  0:32-1:05  1:05-1:48  1:48-2:20      │  │
│  │                                                    │  │
│  │  ┌─ Scene Detail ──────────────────────────────┐  │  │
│  │  │ Scene 2: "Shibuya Crossing"                 │  │  │
│  │  │ Duration: 33s                                │  │  │
│  │  │ Sources: IMG_0234.jpg, VID_0012.mp4         │  │  │
│  │  │ Caption: "The organized chaos of Shibuya"   │  │  │
│  │  │ Transition: Cross-dissolve (1.2s)           │  │  │
│  │  │ [Edit Caption] [Reorder] [Remove]           │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ Generation Pipeline ─────────────────────────────┐  │
│  │ ● Analysis ✓  ● Planning ✓  ○ Reference  ○ Synth │  │
│  │ Step 3/6: Fetching YouTube style references...    │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Sections**:

1. **Concept Prompt Input**
   - `<textarea>` with 2000 char limit
   - Style tag chips (predefined + custom)
   - "Generate Storyboard" button triggers AI pipeline

2. **Google Drive Folder Selector**
   - Opens Google Picker API overlay (sandboxed, no direct Drive browsing)
   - Displays selected folder path, file count, total size
   - Backend validates folder access on selection

3. **AI Storyboard Viewer**
   - Horizontal scrollable timeline with scene cards
   - Click scene → detail panel with metadata, source files, caption
   - Drag-to-reorder scenes (updates storyboard state immutably)
   - Edit caption inline
   - Scene thumbnails generated from source media

4. **Generation Pipeline Status**
   - 6-step stepper (Analysis → Planning → Reference → Synthesis → Encoding → Upload)
   - Active step shows spinner + description
   - SSE-driven real-time updates

#### Export Screen (`/studio/:projectId/export`)

See `docs/phase-04/front-engineer.md` for full export flow specification.

#### Settings Screen (`/settings`)

```
┌─────────────────────────────────────────┐
│  Settings                               │
│─────────────────────────────────────────│
│                                         │
│  Google Drive Connection                │
│  Connected as: user@gmail.com           │
│  [Disconnect]                           │
│                                         │
│  Default Export Settings                │
│  Resolution: [1080p ▼]                  │
│  Format: [MP4 ▼]                        │
│  Captions: [Burned-in ▼]               │
│                                         │
│  Preferences                            │
│  Theme: [System ▼]                      │
│  Language: [English ▼]                  │
│                                         │
│  Danger Zone                            │
│  [Delete All Projects]                  │
└─────────────────────────────────────────┘
```

- No API key input fields in UI — all keys managed server-side via `process.env`
- "Disconnect" revokes Google OAuth token via backend, clears httpOnly cookie

---

## 2. Component Architecture

### 2.1 Atomic Design Hierarchy

#### Atoms (Smallest reusable units)

| Component | Props | Purpose |
|-----------|-------|---------|
| `<Button>` | `variant, size, disabled, onClick, children` | All clickable actions |
| `<Badge>` | `variant: 'success' \| 'warning' \| 'error' \| 'info', label` | Status indicators |
| `<ProgressBar>` | `percent, variant, ariaLabel` | Progress visualization |
| `<Chip>` | `label, removable, onRemove` | Style tags |
| `<Spinner>` | `size` | Loading indicator |
| `<Avatar>` | `src, fallback, size` | User avatar |
| `<Icon>` | `name, size, ariaHidden` | SVG icon wrapper |
| `<TextArea>` | `value, onChange, maxLength, placeholder` | Text input |

#### Molecules (Atom combinations)

| Component | Composition | Purpose |
|-----------|-------------|---------|
| `<StatusBadge>` | `Badge` + `Icon` | Project status display |
| `<ChipGroup>` | `Chip[]` + `Button` (add) | Style tag management |
| `<StepIndicator>` | `Icon` + `Badge` + text | Single pipeline step |
| `<FileInfo>` | `Icon` + text | Folder path + stats |
| `<SearchInput>` | `Input` + `Icon` + `Button` | Filterable search |
| `<ConfirmDialog>` | `Button` + text + `Button` | Destructive action confirmation |

#### Organisms (Complex functional units)

| Component | Composition | Purpose |
|-----------|-------------|---------|
| `<ConceptPromptEditor>` | `TextArea` + `ChipGroup` + `Button` | Prompt + style tag input |
| `<DriveFolderSelector>` | `Button` + `FileInfo` + Google Picker | Select source folder |
| `<StoryboardTimeline>` | `SceneCard[]` + drag handler | Horizontal scene timeline |
| `<SceneDetailPanel>` | `TextArea` + `FileInfo` + `Button[]` | Scene edit panel |
| `<PipelineStepper>` | `StepIndicator[]` + `ProgressBar` | 6-step generation status |
| `<ProjectCard>` | `Image` + `StatusBadge` + `ProgressBar` + text | Dashboard project tile |
| `<ExportModal>` | Selectors + `ProgressBar` + `Button` | Export config + progress |
| `<VideoPlayer>` | `<video>` + controls + overlay | Final vlog preview |
| `<AppHeader>` | `Avatar` + nav + `Button` | Top navigation bar |

#### Templates (Page layouts)

| Template | Layout | Used by |
|----------|--------|---------|
| `<AuthLayout>` | Centered card, no nav | Auth screen |
| `<DashboardLayout>` | Header + grid content | Dashboard |
| `<StudioLayout>` | Header + sidebar + main | Studio, Export |
| `<SettingsLayout>` | Header + single column | Settings |

#### Pages (Route-level components)

| Page | Template | Key Organisms |
|------|----------|---------------|
| `<AuthPage>` | `AuthLayout` | OAuth button, branding |
| `<AuthCallbackPage>` | `AuthLayout` | Spinner (processing) |
| `<DashboardPage>` | `DashboardLayout` | `ProjectCard[]`, filters |
| `<StudioPage>` | `StudioLayout` | `ConceptPromptEditor`, `DriveFolderSelector`, `StoryboardTimeline`, `PipelineStepper` |
| `<ExportPage>` | `StudioLayout` | `ExportModal`, `VideoPlayer` |
| `<SettingsPage>` | `SettingsLayout` | Forms, `ConfirmDialog` |

### 2.2 Key Props Interfaces

```typescript
// All props are readonly — enforcing immutability at the type level

interface ProjectCardProps {
  readonly project: Project;
  readonly onClick: (id: string) => void;
}

interface ConceptPromptEditorProps {
  readonly value: string;
  readonly styleTags: readonly string[];
  readonly onChange: (value: string) => void;
  readonly onStyleTagsChange: (tags: readonly string[]) => void;
  readonly onSubmit: () => void;
  readonly isGenerating: boolean;
}

interface StoryboardTimelineProps {
  readonly scenes: readonly Scene[];
  readonly selectedSceneId: string | null;
  readonly onSelectScene: (id: string) => void;
  readonly onReorderScenes: (fromIndex: number, toIndex: number) => void;
}

interface SceneDetailPanelProps {
  readonly scene: Scene;
  readonly onUpdateCaption: (sceneId: string, caption: string) => void;
  readonly onRemoveScene: (sceneId: string) => void;
}

interface PipelineStepperProps {
  readonly steps: readonly StepProgress[];
  readonly currentStep: ExportStep | null;
  readonly overallPercent: number;
}

interface ExportModalProps {
  readonly isOpen: boolean;
  readonly onClose: () => void;
  readonly onExport: (config: ExportConfig) => void;
  readonly defaultConfig: ExportConfig;
  readonly estimatedDuration?: number;
}
```

### 2.3 Directory Structure

```
src/
├── components/
│   ├── atoms/
│   │   ├── Button/
│   │   │   ├── Button.tsx
│   │   │   ├── Button.test.tsx
│   │   │   └── index.ts
│   │   ├── Badge/
│   │   ├── ProgressBar/
│   │   ├── Chip/
│   │   ├── Spinner/
│   │   ├── Icon/
│   │   └── TextArea/
│   ├── molecules/
│   │   ├── StatusBadge/
│   │   ├── ChipGroup/
│   │   ├── StepIndicator/
│   │   └── FileInfo/
│   ├── organisms/
│   │   ├── ConceptPromptEditor/
│   │   ├── DriveFolderSelector/
│   │   ├── StoryboardTimeline/
│   │   ├── SceneDetailPanel/
│   │   ├── PipelineStepper/
│   │   ├── ProjectCard/
│   │   ├── ExportModal/
│   │   ├── VideoPlayer/
│   │   └── AppHeader/
│   ├── templates/
│   │   ├── AuthLayout.tsx
│   │   ├── DashboardLayout.tsx
│   │   ├── StudioLayout.tsx
│   │   └── SettingsLayout.tsx
│   └── pages/
│       ├── AuthPage.tsx
│       ├── AuthCallbackPage.tsx
│       ├── DashboardPage.tsx
│       ├── StudioPage.tsx
│       ├── ExportPage.tsx
│       └── SettingsPage.tsx
├── hooks/
│   ├── useAuth.ts
│   ├── useProjects.ts
│   ├── useStoryboard.ts
│   ├── useExportProgress.ts
│   └── useDrivePicker.ts
├── stores/
│   ├── authStore.ts
│   └── studioStore.ts
├── api/
│   ├── client.ts
│   ├── auth.ts
│   ├── projects.ts
│   ├── storyboard.ts
│   └── export.ts
├── types/
│   ├── project.ts
│   ├── storyboard.ts
│   ├── export.ts
│   └── auth.ts
├── utils/
│   ├── sse.ts
│   └── validation.ts
├── router.tsx
└── App.tsx
```

---

## 3. State Management

### 3.1 Recommendation

**Zustand for client state + TanStack Query (React Query) for server state.**

| Concern | Solution | Why |
|---------|----------|-----|
| Auth status | Zustand | Synchronous, rarely changes, drives route guards |
| Project list | TanStack Query | Server data, needs caching, pagination, refetch |
| Current storyboard | TanStack Query + Zustand | Fetched from server, edited locally with undo |
| Export progress | Zustand (SSE-fed) | Streaming real-time data, not request/response |
| UI state (modals, selections) | Zustand | Ephemeral, local-only |

**Why not Redux Toolkit**: Overkill for this app. Zustand provides the same immutable update patterns with less boilerplate. TanStack Query handles the server-cache synchronization that Redux Toolkit Query would otherwise provide.

### 3.2 Auth State

```typescript
// stores/authStore.ts
import { create } from 'zustand';

interface AuthState {
  readonly isAuthenticated: boolean;
  readonly user: AuthUser | null;
  readonly isLoading: boolean;
}

interface AuthActions {
  readonly setAuthenticated: (user: AuthUser) => void;
  readonly setUnauthenticated: () => void;
  readonly setLoading: (loading: boolean) => void;
}

interface AuthUser {
  readonly email: string;
  readonly name: string;
  readonly avatarUrl: string;
}

export const useAuthStore = create<AuthState & AuthActions>((set) => ({
  isAuthenticated: false,
  user: null,
  isLoading: true,

  setAuthenticated: (user) =>
    set({ isAuthenticated: true, user, isLoading: false }),

  setUnauthenticated: () =>
    set({ isAuthenticated: false, user: null, isLoading: false }),

  setLoading: (isLoading) => set({ isLoading }),
}));
```

**Token handling**: No tokens in frontend state. The backend sets `httpOnly` + `Secure` + `SameSite=Strict` cookies. The frontend only knows `isAuthenticated` (verified via `GET /api/v1/auth/me`).

### 3.3 Project State (TanStack Query)

```typescript
// hooks/useProjects.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsApi } from '../api/projects';

export function useProjects(filter?: ProjectFilter) {
  return useQuery({
    queryKey: ['projects', filter],
    queryFn: () => projectsApi.list(filter),
    staleTime: 30_000,           // 30s before refetch
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: projectsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

export function useProject(projectId: string) {
  return useQuery({
    queryKey: ['projects', projectId],
    queryFn: () => projectsApi.get(projectId),
    enabled: !!projectId,
  });
}
```

### 3.4 Storyboard State (Immutable with Undo)

```typescript
// stores/studioStore.ts
import { create } from 'zustand';
import type { Scene } from '../types/storyboard';

const MAX_UNDO_HISTORY = 50;

interface StudioState {
  readonly scenes: readonly Scene[];
  readonly selectedSceneId: string | null;
  readonly history: readonly (readonly Scene[])[];  // undo stack, capped at MAX_UNDO_HISTORY
  readonly historyIndex: number;
}

interface StudioActions {
  readonly setScenes: (scenes: readonly Scene[]) => void;
  readonly selectScene: (id: string | null) => void;
  readonly updateCaption: (sceneId: string, caption: string) => void;
  readonly reorderScenes: (fromIndex: number, toIndex: number) => void;
  readonly removeScene: (sceneId: string) => void;
  readonly undo: () => void;
  readonly redo: () => void;
}

export const useStudioStore = create<StudioState & StudioActions>((set, get) => ({
  scenes: [],
  selectedSceneId: null,
  history: [],
  historyIndex: -1,

  setScenes: (scenes) =>
    set({ scenes, history: [scenes], historyIndex: 0 }),

  selectScene: (id) =>
    set({ selectedSceneId: id }),

  // Helper: push to history with cap at MAX_UNDO_HISTORY
  // Drops oldest entries when limit exceeded to prevent memory bloat
  _pushHistory: (nextScenes: readonly Scene[]) => {
    const { history, historyIndex } = get();
    const trimmed = history.slice(0, historyIndex + 1);
    const nextHistory = trimmed.length >= MAX_UNDO_HISTORY
      ? [...trimmed.slice(trimmed.length - MAX_UNDO_HISTORY + 1), nextScenes]
      : [...trimmed, nextScenes];
    return {
      scenes: nextScenes,
      history: nextHistory,
      historyIndex: nextHistory.length - 1,
    };
  },

  updateCaption: (sceneId, caption) => {
    const { scenes, _pushHistory } = get();
    const nextScenes = scenes.map((scene) =>
      scene.id === sceneId ? { ...scene, caption } : scene
    );
    set(_pushHistory(nextScenes));
  },

  reorderScenes: (fromIndex, toIndex) => {
    const { scenes, _pushHistory } = get();
    const nextScenes = [...scenes];
    const [moved] = nextScenes.splice(fromIndex, 1);
    nextScenes.splice(toIndex, 0, moved);
    const frozen = Object.freeze(nextScenes);
    set(_pushHistory(frozen));
  },

  removeScene: (sceneId) => {
    const { scenes, _pushHistory } = get();
    const nextScenes = scenes.filter((s) => s.id !== sceneId);
    set({ ..._pushHistory(nextScenes), selectedSceneId: null });
  },

  undo: () => {
    const { history, historyIndex } = get();
    if (historyIndex > 0) {
      set({
        scenes: history[historyIndex - 1],
        historyIndex: historyIndex - 1,
      });
    }
  },

  redo: () => {
    const { history, historyIndex } = get();
    if (historyIndex < history.length - 1) {
      set({
        scenes: history[historyIndex + 1],
        historyIndex: historyIndex + 1,
      });
    }
  },
}));
```

### 3.5 Export Progress State (SSE-fed)

```typescript
// hooks/useExportProgress.ts
import { useEffect, useCallback } from 'react';
import { create } from 'zustand';
import type { ExportProgress } from '../types/export';

interface ExportProgressState {
  readonly progress: ExportProgress | null;
  readonly connectionStatus: 'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'failed';
}

interface ExportProgressActions {
  readonly setProgress: (progress: ExportProgress) => void;
  readonly setConnectionStatus: (status: ExportProgressState['connectionStatus']) => void;
  readonly reset: () => void;
}

export const useExportProgressStore = create<ExportProgressState & ExportProgressActions>(
  (set) => ({
    progress: null,
    connectionStatus: 'disconnected',

    setProgress: (progress) => set({ progress }),
    setConnectionStatus: (connectionStatus) => set({ connectionStatus }),
    reset: () => set({ progress: null, connectionStatus: 'disconnected' }),
  })
);

export function useExportProgressSSE(jobId: string | null) {
  const { setProgress, setConnectionStatus, reset } = useExportProgressStore();

  useEffect(() => {
    if (!jobId) return;

    let consecutiveErrors = 0;
    const MAX_CONSECUTIVE_ERRORS = 5;

    const source = new EventSource(`/api/v1/export/${jobId}/progress`, {
      withCredentials: true,
    });

    source.onopen = () => {
      consecutiveErrors = 0;  // reset on successful connection
      setConnectionStatus('connected');
    };

    source.onmessage = (event) => {
      consecutiveErrors = 0;  // reset on successful message
      const data: ExportProgress = JSON.parse(event.data);
      setProgress(data);

      if (data.status === 'completed' || data.status === 'failed') {
        source.close();
        setConnectionStatus('disconnected');
      }
    };

    source.onerror = () => {
      consecutiveErrors++;

      if (source.readyState === EventSource.CONNECTING) {
        // EventSource is auto-reconnecting — show "reconnecting" state
        setConnectionStatus('reconnecting');
      } else if (
        source.readyState === EventSource.CLOSED ||
        consecutiveErrors >= MAX_CONSECUTIVE_ERRORS
      ) {
        // Fatal: connection closed by server or too many retries
        // User must manually retry via fallback polling
        source.close();
        setConnectionStatus('failed');
      }
    };

    setConnectionStatus('connecting');

    return () => {
      source.close();
      reset();
    };
  }, [jobId, setProgress, setConnectionStatus, reset]);
}

// Fallback: poll for progress when SSE fails permanently
export function useExportProgressPolling(
  jobId: string | null,
  enabled: boolean  // only enable when SSE connectionStatus === 'failed'
) {
  const { setProgress } = useExportProgressStore();

  useEffect(() => {
    if (!jobId || !enabled) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/v1/export/${jobId}/result`, {
          credentials: 'include',
        });
        if (res.ok) {
          const data: ExportProgress = await res.json();
          setProgress(data);
          if (data.status === 'completed' || data.status === 'failed') {
            clearInterval(interval);
          }
        }
      } catch {
        // Silently continue polling
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [jobId, enabled, setProgress]);
}
```

---

## 4. API Integration Layer

### 4.1 HTTP Client

```typescript
// api/client.ts
const BASE_URL = '/api/v1';

interface RequestConfig {
  readonly method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  readonly path: string;
  readonly body?: unknown;
  readonly signal?: AbortSignal;
}

async function request<T>(config: RequestConfig): Promise<T> {
  const response = await fetch(`${BASE_URL}${config.path}`, {
    method: config.method,
    headers: config.body ? { 'Content-Type': 'application/json' } : {},
    body: config.body ? JSON.stringify(config.body) : undefined,
    credentials: 'include',          // sends httpOnly cookies
    signal: config.signal,
  });

  if (response.status === 401) {
    // Trigger auth store reset → redirect to /auth
    window.location.href = '/auth';
    throw new ApiError('UNAUTHORIZED', 'Session expired');
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ApiError(
      errorBody.code ?? 'UNKNOWN',
      errorBody.message ?? `Request failed: ${response.status}`
    );
  }

  return response.json();
}

class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export const apiClient = {
  get: <T>(path: string, signal?: AbortSignal) =>
    request<T>({ method: 'GET', path, signal }),
  post: <T>(path: string, body?: unknown) =>
    request<T>({ method: 'POST', path, body }),
  put: <T>(path: string, body?: unknown) =>
    request<T>({ method: 'PUT', path, body }),
  delete: <T>(path: string) =>
    request<T>({ method: 'DELETE', path }),
};
```

### 4.2 Complete Endpoint Catalog

| Method | Endpoint | Request | Response | Used By |
|--------|----------|---------|----------|---------|
| **Auth** |
| POST | `/auth/token` | `{ code, codeVerifier }` | Sets httpOnly cookie + `{ user }` | AuthCallback |
| GET | `/auth/me` | — | `{ user }` or 401 | AuthGuard |
| POST | `/auth/logout` | — | Clears cookie | Settings |
| **Projects** |
| GET | `/projects` | `?status=&cursor=&limit=` | `{ projects[], nextCursor }` | Dashboard |
| POST | `/projects` | `{ title, folderId, prompt, styleTags }` | `{ project }` | Dashboard |
| GET | `/projects/:id` | — | `{ project }` | Studio |
| PUT | `/projects/:id` | `{ title?, prompt?, styleTags? }` | `{ project }` | Studio |
| DELETE | `/projects/:id` | — | 204 | Dashboard |
| **Storyboard** |
| POST | `/projects/:id/generate` | `{ prompt, styleTags, folderId }` | `{ jobId }` (starts pipeline) | Studio |
| GET | `/projects/:id/storyboard` | — | `{ scenes[] }` | Studio |
| PUT | `/projects/:id/storyboard` | `{ scenes[] }` | `{ scenes[] }` | Studio (save edits) |
| **Export** |
| POST | `/export` | `{ projectId, resolution, format, captions, bgmVolume }` | `{ jobId }` | Export |
| GET | `/export/:jobId/progress` | — | SSE stream | Export |
| POST | `/export/:jobId/cancel` | — | 204 | Export |
| GET | `/export/:jobId/result` | — | `{ url, driveUrl?, size, duration }` | Export |
| POST | `/export/estimate` | `{ projectId, resolution, format }` | `{ estimatedSeconds }` | Export |
| **Drive** |
| GET | `/drive/folders` | `?parentId=` | `{ folders[] }` | DriveFolderSelector |
| GET | `/drive/folders/:id/stats` | — | `{ fileCount, totalSize }` | DriveFolderSelector |
| **Settings** |
| GET | `/settings` | — | `{ preferences }` | Settings |
| PUT | `/settings` | `{ preferences }` | `{ preferences }` | Settings |

### 4.3 Error Handling Strategy

```typescript
// Three-tier error handling:

// Tier 1: API client (automatic)
// - 401 → redirect to /auth
// - Network errors → throw with retryable flag

// Tier 2: TanStack Query (automatic)
// - Retry 3x with exponential backoff for network errors
// - No retry for 4xx errors

// Tier 3: Component-level (manual)
// - Display user-friendly error messages via toast
// - Provide retry action for retryable errors
// - Log to console in development only

// TanStack Query global config
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        if (error instanceof ApiError && error.code === 'UNAUTHORIZED') {
          return false;
        }
        return failureCount < 3;
      },
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10000),
      staleTime: 30_000,
    },
    mutations: {
      retry: false,
    },
  },
});
```

### 4.4 Loading & Skeleton Strategy

| Screen | Loading State |
|--------|---------------|
| Dashboard | Grid of skeleton `ProjectCard` shapes (pulse animation) |
| Studio | Skeleton textarea + empty timeline placeholder |
| Storyboard | Skeleton scene cards on timeline |
| Export | Spinner overlay on export modal |

TanStack Query provides `isLoading`, `isFetching`, `isError` flags for each query. Components render skeleton variants when `isLoading` is true.

### 4.5 Optimistic Updates

Applied only where latency impact is noticeable and rollback is safe:

| Action | Optimistic? | Why |
|--------|-------------|-----|
| Reorder scenes | Yes | Drag-and-drop must feel instant |
| Edit caption | Yes | Inline text editing must be responsive |
| Delete project | No | Destructive — wait for confirmation |
| Start export | No | Long-running — no instant feedback expected |

```typescript
// Example: optimistic caption update
useMutation({
  mutationFn: (params: { sceneId: string; caption: string }) =>
    storyboardApi.updateScene(projectId, params),
  onMutate: async ({ sceneId, caption }) => {
    await queryClient.cancelQueries({ queryKey: ['storyboard', projectId] });
    const previous = queryClient.getQueryData(['storyboard', projectId]);

    // Optimistic update (immutable)
    queryClient.setQueryData(['storyboard', projectId], (old: Storyboard) => ({
      ...old,
      scenes: old.scenes.map((s) =>
        s.id === sceneId ? { ...s, caption } : s
      ),
    }));

    return { previous };
  },
  onError: (_err, _vars, context) => {
    // Rollback on failure
    queryClient.setQueryData(['storyboard', projectId], context?.previous);
  },
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: ['storyboard', projectId] });
  },
});
```

---

## 5. Security: XSS Sanitization Policy

> **Conclusion**: No `dangerouslySetInnerHTML` anywhere in the codebase. All user-generated text (prompts, captions, titles) is rendered as plain text via JSX interpolation, which React auto-escapes. Zod validates all API responses at the boundary.

### 5.1 Rendering Rules (Mandatory)

| Content Type | Rendering Method | XSS Risk |
|---|---|---|
| Concept prompt | `{project.prompt}` in JSX | None — React escapes |
| Scene captions | `{scene.caption}` in JSX | None — React escapes |
| Project titles | `{project.title}` in JSX | None — React escapes |
| Style tag chips | `{tag}` inside `<Chip>` | None — React escapes |
| Error messages from API | `{error.message}` in JSX | None — React escapes |

### 5.2 Banned Patterns

```typescript
// BANNED — never use in this project
dangerouslySetInnerHTML    // No raw HTML injection, ever
innerHTML                  // No DOM manipulation with user content
document.write             // No document-level injection
eval()                     // No dynamic code execution
new Function()             // No dynamic code execution
```

**ESLint enforcement**:
```json
{
  "rules": {
    "react/no-danger": "error",
    "no-eval": "error",
    "no-new-func": "error"
  }
}
```

### 5.3 Rich Caption Formatting

If future requirements demand rich text captions (bold, italic, links):
- Use a **whitelist-based Markdown-to-JSX renderer** (e.g., `react-markdown` with `allowedElements` restricted to `['strong', 'em', 'p', 'br']`)
- NEVER parse HTML directly — only Markdown subset
- Strip all HTML tags from API responses at the API client layer before caching

### 5.4 API Response Validation

All API responses are validated with Zod schemas before entering state:

```typescript
// api/projects.ts
import { z } from 'zod';

const ProjectSchema = z.object({
  id: z.string().uuid(),
  title: z.string().max(200),
  status: z.enum(['draft', 'processing', 'ready', 'failed']),
  prompt: z.string().max(2000),
  styleTags: z.array(z.string().max(50)).max(20),
  // ... other fields
});

// Parse response — rejects unexpected shapes or injected fields
export async function getProject(id: string): Promise<Project> {
  const raw = await apiClient.get(`/projects/${id}`);
  return ProjectSchema.parse(raw);
}
```

This prevents malformed or injected API responses (e.g., from a compromised CDN or MITM) from reaching the rendering layer.

---

## 6. Accessibility & Performance

### 6.1 WCAG 2.1 AA Compliance

| Requirement | Implementation |
|-------------|----------------|
| **Color contrast** | Minimum 4.5:1 for text, 3:1 for large text/UI components |
| **Keyboard navigation** | All interactive elements focusable; logical tab order; focus trapping in modals |
| **Screen readers** | Semantic HTML (`<main>`, `<nav>`, `<section>`); ARIA labels on icons/buttons; live regions for progress updates |
| **Focus management** | Focus moves to new content on route change; returns to trigger on modal close |
| **Motion** | Respect `prefers-reduced-motion`; disable animations/transitions when set |
| **Forms** | All inputs have visible labels; error messages linked via `aria-describedby` |
| **Images** | Alt text on all thumbnails; decorative images use `aria-hidden` |

**Progress-specific accessibility**:
```tsx
<div
  role="progressbar"
  aria-valuenow={percent}
  aria-valuemin={0}
  aria-valuemax={100}
  aria-label={`Export progress: ${percent}%`}
/>

<div aria-live="polite" className="sr-only">
  {`Now ${currentStep}: ${stepDescription}`}
</div>
```

### 6.2 Code Splitting & Lazy Loading

```typescript
// router.tsx
import { lazy, Suspense } from 'react';

const DashboardPage = lazy(() => import('./components/pages/DashboardPage'));
const StudioPage = lazy(() => import('./components/pages/StudioPage'));
const ExportPage = lazy(() => import('./components/pages/ExportPage'));
const SettingsPage = lazy(() => import('./components/pages/SettingsPage'));

// Auth pages loaded eagerly (small, always needed first)
import { AuthPage } from './components/pages/AuthPage';
import { AuthCallbackPage } from './components/pages/AuthCallbackPage';
```

**Split boundaries**:
| Bundle | Contents | Estimated Size |
|--------|----------|----------------|
| `main` | Auth, router, atoms, API client, stores | ~40KB gzipped |
| `dashboard` | DashboardPage + ProjectCard | ~15KB gzipped |
| `studio` | StudioPage + StoryboardTimeline + editor | ~35KB gzipped |
| `export` | ExportPage + VideoPlayer + progress | ~25KB gzipped |
| `settings` | SettingsPage + forms | ~8KB gzipped |

### 6.3 Core Web Vitals Targets

| Metric | Target | Strategy |
|--------|--------|----------|
| **LCP** (Largest Contentful Paint) | < 2.5s | Skeleton screens; preload critical fonts; server-render auth check |
| **FID** (First Input Delay) | < 100ms | Code splitting; no heavy computation on main thread |
| **CLS** (Cumulative Layout Shift) | < 0.1 | Fixed dimensions on skeleton cards; explicit `width`/`height` on images |
| **INP** (Interaction to Next Paint) | < 200ms | Optimistic updates on drag/edit; `useTransition` for non-urgent updates |

### 6.4 Additional Performance Measures

- **Image optimization**: Thumbnails served as WebP with `srcset` for responsive sizes
- **Prefetching**: Prefetch `/studio/:id` data on project card hover (`queryClient.prefetchQuery`)
- **SSE efficiency**: Single SSE connection per export job; closed immediately on completion
- **Memory**: StoryboardTimeline virtualizes scene list if > 50 scenes (react-window)
- **Service Worker**: Cache static assets (JS, CSS, fonts) for offline shell; API responses not cached

---

## Appendix: Type Definitions

```typescript
// types/project.ts
interface Project {
  readonly id: string;
  readonly title: string;
  readonly status: 'draft' | 'processing' | 'ready' | 'failed';
  readonly prompt: string;
  readonly styleTags: readonly string[];
  readonly folderId: string;
  readonly folderPath: string;
  readonly thumbnail?: string;
  readonly duration?: number;
  readonly createdAt: string;
  readonly updatedAt: string;
}

// types/storyboard.ts
interface Scene {
  readonly id: string;
  readonly index: number;
  readonly title: string;
  readonly caption: string;
  readonly startTime: number;     // seconds
  readonly endTime: number;       // seconds
  readonly sourceFiles: readonly SourceFile[];
  readonly transition: Transition;
  readonly thumbnail?: string;
}

interface SourceFile {
  readonly driveFileId: string;
  readonly name: string;
  readonly type: 'image' | 'video';
  readonly mimeType: string;
}

interface Transition {
  readonly type: 'cut' | 'cross-dissolve' | 'fade-black' | 'wipe';
  readonly duration: number;      // seconds
}

// types/export.ts
interface ExportConfig {
  readonly projectId: string;
  readonly resolution: '720p' | '1080p' | '4k';
  readonly format: 'mp4' | 'webm';
  readonly captions: 'burned-in' | 'srt' | 'none';
  readonly bgmVolume: number;     // 0–100
  readonly destination: 'download' | 'drive' | 'both';
}

interface ExportResult {
  readonly jobId: string;
  readonly downloadUrl: string;
  readonly driveUrl?: string;
  readonly fileSize: number;
  readonly duration: number;
  readonly expiresAt: string;
}

// types/auth.ts
interface AuthUser {
  readonly email: string;
  readonly name: string;
  readonly avatarUrl: string;
}
```
