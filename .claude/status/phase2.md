# Phase 2: Narrative & Reference (Step 03-04)

## 🎯 Phase KPIs
- [ ] **Storyboard Coherence**: Out-of-sequence errors in chronological flow < 10%
- [ ] **Contextual Cut Precision**: Selection of clip start/end points based on narrative importance > 90% accuracy
- [ ] **Search Relevance**: Cosine similarity between Top 3 YouTube results and storyboard prompt > 0.75

---

## 👨‍💻 Agent Task Delegation

Based on the 6-agent developer team architecture, here are the detailed implementation tasks for Phase 2.

### 1. Team Leader
- **Orchestration**: Ensure the storyboarding JSON schema is robust enough to convey pacing, audio, and visual transitions.
- **Quality Assurance**: Manually review storyboard coherence out-of-sequence rates against the 10% KPI limit.

### 2. FrontEngineer
- **UI/UX**: Develop an interactive Storyboard Review UI where users can see the proposed narrative flow (thumbnails, text summaries).
- **Interactivity**: Allow users to drag-and-drop or modify the narrative before it gets sent to the rendering pipeline.

### 3. BackendEngineer
- **API Endpoints**: Build endpoints to save, retrieve, and update storyboards in the database.
- **Integration**: Build the YouTube Data API v3 integration wrapper to securely fetch video references without exhausting API quotas.

### 4. AI Engineer
- **Storyboarding Logic**: Write the prompt and parsing logic that converts Phase 1 "Key Moment" tags into a highly coherent narrative arc.
- **Alignment**: Ensure the generated narrative strictly adheres to the user's initial "concept prompt".
- **Temporal Calculation**: Write Python scripts to calculate exact video timing and duration logic (avoiding LLM mental math).
- **AI Pacing**: Implement the "Context-Aware Trimming" algorithm to automatically identify the 90%+ precise clip start and end Cut Points to preserve scene context.
- **Reference Scoring**: Implement the Cosine Similarity calculation to ensure YouTube semantic visual references exceed the 0.75 relevance KPI.

### 5. Devops/QA Engineer
- **Integration Testing**: Write tests affirming that the Narrative endpoints successfully execute the YouTube API logic.
- **Data Mocks**: Provide deterministic mock datasets of Gemini tags for the LLM Engineer and ML Scientist to build their logic reliably in CI.
