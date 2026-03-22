# Phase 1: Data & Analysis Demo (PoC)

Follow these instructions to run the Proof of Concept.

## 1. Start Infrastructure

Navigate to the project root and start the Docker containers:

```bash
cd /Users/dalssung/Desktop/project/TripVlog_gogle
docker compose up -d
```

## 2. Install Dependencies

Install the necessary dependencies for both the backend and AI service.

```bash
# Backend (includes supertest)
cd backend && npm install

# AI Service
cd ../ai-service && pip install -r requirements.txt

# macOS optional requirements
brew install exempi ffmpeg
```

## 3. Run the AI Pipeline Demo

Navigate to the `ai-service` directory to run the demo. The demo calls `/analyze` (EXIF + geocoding) then `/storyboard` (GPS clustering + Gemini + assembly) entirely in-process.

It will print the full JSON from both endpoints and a scene summary table (ID · type · duration · quality score · caption).

```bash
cd ai-service

# Mock mode (no API key needed — recommended for the first run)
python demo.py

# Live mode (requires a real Gemini 1.5 Pro API key)
GEMINI_API_KEY=your-key python demo.py
```

## 4. Run All Tests

To run the complete test suite (Backend: Jest with 5 test files, AI Service: Pytest with 77 tests):

```bash
cd /Users/dalssung/Desktop/project/TripVlog_gogle
bash scripts/run-tests.sh
```