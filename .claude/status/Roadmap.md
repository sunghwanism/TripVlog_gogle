# KPI and Developing Step

> **📍 CURRENT CHECKPOINT:** `Phase 1: Data & Analysis - Implement OAuth2 flow`
> *Update this checkpoint as tasks are completed to notify the agents of the current active step.*
> **🛠️ Agent Optimization Status:** All `.claude/` directory `skills`, `rules`, `hooks`, and `scripts` have been successfully mapped to the 6 developer agents in the team configuration.

## Step-by-step KPI

### Phase 1: Data & Analysis
- [ ] **Metadata Integrity**: Extraction success rate for GPS and timestamp data > 99.5%
- [ ] **Analysis Precision**: F1-score for "Key Moment" tagging > 0.85 (compared to human baseline)
- [ ] **Latency**: Analysis completion time < 30s for 10 raw clips

### Phase 2: Narrative & Reference
- [ ] **Storyboard Coherence**: Out-of-sequence errors in chronological flow < 10%
- [ ] **Contextual Cut Precision**: Selection of clip start/end points based on narrative importance > 90% accuracy
- [ ] **Search Relevance**: Cosine similarity between Top 3 YouTube results and storyboard prompt > 0.75

### Phase 3: Synthesis & Audio (Focus: Natural Stitching)
- [ ] **Visual Continuity**: Natural flow between clips using dissolve transitions (No awkward jumps)
- [ ] **Transition Smoothness**: Flicker or artifact rate during dissolve effects < 1%
- [ ] **Audio Sync**: BGM "drops" or transitions aligned within ±50ms of visual scene changes

### Phase 4: Encoding & Deployment
- [ ] **Render Throughput**: Final 60s vlog rendering and upload < 3 minutes
- [ ] **Upload Success**: 100% success rate for returning final file links to users

---

## Road Map

### 1. Phase 1: Data & Analysis (Step 01-02)
- [ ] **Implement OAuth2 flow**: Establish secure Google Drive access and permissions.
- [ ] **Metadata Extraction**: Develop a robust engine for XMP/EXIF data extraction.
- [ ] **Gemini 1.5 Pro Wrapper**: Automate frame-by-frame analysis and landmark tagging.

### 2. Phase 2: Narrative & Reference (Step 03-04)
- [ ] **Storyboarding Agent**: Design narrative arcs
- [ ] **Context-Aware Trimming**: Identify optimal "Cut Points" to preserve scene context and narrative flow.
- [ ] **YouTube API Integration**: Secure visual reference data via YouTube Data API v3.
- [ ] **Temporal Calculation**: Integrate video duration and timing logic

### 3. Phase 3: Synthesis & Audio (Step 05-06)
- [ ] **Stitching Pipeline**: Build a TDD-based pipeline focused on concatenating raw clips (80% coverage).
- [ ] **Contextual Dissolve**: Implement natural cross-dissolve transitions between original clips for seamless flow.
- [ ] **Audio & Caption**: Develop BGM generation and metadata-driven caption overlays.

### 4. Phase 4: Encoding & Deployment (Step 07)
- [ ] **Cloud FFmpeg**: Architect a cloud-based encoding pipeline (GCP Cloud Run) for final concatenation.
- [ ] **CI/CD Automation**: Implement automated upload and Drive sync