# Phase 1: Data & Analysis (Step 01-02)

## 🎯 Phase KPIs
- [ ] **Metadata Integrity**: Extraction success rate for GPS and timestamp data > 99.5%
- [ ] **Analysis Precision**: F1-score for "Key Moment" tagging via LLM > 0.85 (compared to human baseline)
- [ ] **Latency**: Analysis completion time < 30s for 10 raw clips

---

## 👨‍💻 Agent Task Delegation

Based on the 6-agent developer team architecture, here are the detailed implementation tasks for Phase 1.

### 1. Team Leader
- **Orchestration**: Review the data schema for metadata extraction and Gemini 1.5 Pro analysis to ensure it perfectly supports downstream phases.
- **Review**: Conduct Code Reviews on OAuth implementations to ensure Google Drive scopes are minimal and secure.

### 2. FrontEngineer
- **UI/UX**: Build the "Connect to Google Drive" UI utilizing standard OAuth2 popup flows.
- **State Management**: Create a loading and progress state UI for the "Footage Analysis" loading screen to keep users engaged while waiting for the < 30s latency KPI.
- **Folder Selection**: Implement a robust React/Vue tree-view component for selecting the target raw footage folder.

### 3. BackendEngineer
- **Authentication**: Implement OAuth2 server-side validation and secure token storage (in memory/env, NO code hardcoding).
- **Drive Integration**: Write the Google Drive API wrapper to securely fetch and stream clips from the selected folder.
- **Metadata Logic**: Implement the core extraction engine to pull XMP/EXIF (GPS and timestamps) from video buffers before passing it to the LLM.

### 4. AI Engineer
- **AI Wrapper**: Implement the API client for Gemini 1.5 Pro.
- **Prompt Engineering**: Write the prompt logic to analyze video frames and intelligently identify and tag "Key Moments".
- **Data Validation**: Ensure the Gemini output accurately maps to the expected JSON schema with an F1-score > 0.85 for precision.
- **Synthesis Planning**: Define the required tags and context markers needed for downstream Veo 3 synthesis in Phase 3.

### 5. Devops/QA Engineer
- **Security Check**: Verify that secret keys for Drive and Gemini do not leak in any API responses.
- **Testing**: Write automated API unit tests verifying the >99.5% metadata integrity KPI using mock video files.
- **CI/CD**: Configure the initial deployment environment for the backend and frontend repositories.
