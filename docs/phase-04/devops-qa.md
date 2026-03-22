# Phase 04: Encoding & Deploy — DevOps/QA Perspective

> **Conclusion**: Phase 04 delivers the final encoded video to users via a CI/CD pipeline on GitHub Actions, deploys to Cloud Run with canary traffic splitting, and gates all releases behind Playwright E2E tests achieving 80%+ coverage.

---

## 1. Final Encoding Pipeline

### Export Profiles

| Profile | Codec | Resolution | Bitrate | Container | Use Case |
|---------|-------|-----------|---------|-----------|----------|
| web-hd | H.264 (libx264) | 1920x1080 | 8 Mbps | MP4 | Default download |
| web-4k | H.265 (libx265) | 3840x2160 | 20 Mbps | MP4 | Premium users |
| social | H.264 | 1080x1920 | 6 Mbps | MP4 | Vertical/Stories |
| preview | H.264 | 854x480 | 2 Mbps | MP4 | Preview before export |

### FFmpeg Final Export Command

```bash
# web-hd profile
ffmpeg -i input.mkv \
  -c:v libx264 -preset slow -b:v 8M -maxrate 10M -bufsize 16M \
  -c:a aac -b:a 192k -ar 48000 \
  -movflags +faststart \
  -f mp4 output.mp4
```

`-movflags +faststart` is critical — it moves the MOOV atom to the beginning of the file for progressive web playback.

---

## 2. CI/CD Pipeline (GitHub Actions)

### Pipeline Overview

```
PR opened/updated
  ├── lint (ESLint + Prettier + Ruff)          [~1 min]
  ├── type-check (tsc --noEmit + mypy)         [~1 min]
  ├── secret-scan (gitleaks)                    [~30s]
  ├── unit-tests (Jest + pytest, parallel)      [~3 min]
  └── build (Docker image, no push)             [~2 min]
        │
        ▼ (all pass → merge to main)
  ├── build + push to Artifact Registry         [~3 min]
  ├── deploy to staging (Cloud Run, 100%)       [~2 min]
  ├── integration tests (staging)               [~5 min]
  ├── e2e tests (Playwright, staging)           [~8 min]
  └── deploy to production (canary 10%)         [~2 min]
        │
        ▼ (smoke tests pass)
  └── promote to 100% traffic                   [~1 min]
```

### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI Pipeline

on:
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
      - run: npm run lint
      - run: npx prettier --check .

  type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
      - run: npx tsc --noEmit

  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  unit-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        shard: [1, 2, 3]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: npm ci
      - run: pip install -r requirements.txt
      - run: npm run test -- --shard=${{ matrix.shard }}/3 --coverage
      - run: pytest tests/ --cov --cov-report=xml -x

  build:
    runs-on: ubuntu-latest
    needs: [lint, type-check, secret-scan, unit-tests]
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t tripvlog-api:${{ github.sha }} -f Dockerfile.api .
      - run: docker build -t tripvlog-worker:${{ github.sha }} -f Dockerfile.worker .
```

```yaml
# .github/workflows/deploy.yml
name: Deploy Pipeline

on:
  push:
    branches: [main]

jobs:
  build-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SA }}
      - uses: google-github-actions/setup-gcloud@v2
      - run: gcloud auth configure-docker us-central1-docker.pkg.dev
      - run: |
          docker build -t us-central1-docker.pkg.dev/$PROJECT_ID/tripvlog/api:${{ github.sha }} -f Dockerfile.api .
          docker push us-central1-docker.pkg.dev/$PROJECT_ID/tripvlog/api:${{ github.sha }}

  deploy-staging:
    needs: build-push
    runs-on: ubuntu-latest
    steps:
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SA }}
      - run: |
          gcloud run deploy tripvlog-api-staging \
            --image us-central1-docker.pkg.dev/$PROJECT_ID/tripvlog/api:${{ github.sha }} \
            --region us-central1 \
            --set-env-vars "NODE_ENV=staging"

  e2e-tests:
    needs: deploy-staging
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
      - run: npx playwright install --with-deps chromium
      - run: npx playwright test --project=chromium
        env:
          BASE_URL: ${{ secrets.STAGING_URL }}
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-report
          path: playwright-report/

  deploy-production:
    needs: e2e-tests
    runs-on: ubuntu-latest
    steps:
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SA }}
      # Canary: 10% traffic to new revision
      - run: |
          gcloud run deploy tripvlog-api \
            --image us-central1-docker.pkg.dev/$PROJECT_ID/tripvlog/api:${{ github.sha }} \
            --region us-central1 \
            --tag canary \
            --no-traffic
      - run: |
          gcloud run services update-traffic tripvlog-api \
            --region us-central1 \
            --to-tags canary=10

  smoke-and-promote:
    needs: deploy-production
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npx playwright test tests/smoke/ --project=chromium
        env:
          BASE_URL: ${{ secrets.PRODUCTION_URL }}
      # Promote to 100% on success
      - run: |
          gcloud run services update-traffic tripvlog-api \
            --region us-central1 \
            --to-latest
```

---

## 3. E2E Test Strategy (Playwright)

### Test Scenarios

```typescript
// tests/e2e/happy-path.spec.ts
test.describe('Vlog Generation - Happy Path', () => {
  test('user creates project and generates vlog', async ({ page }) => {
    // 1. Login with Google OAuth (mocked via test account)
    await page.goto('/login');
    await page.click('[data-testid="google-login"]');

    // 2. Create new project
    await page.click('[data-testid="new-project"]');
    await page.fill('[data-testid="project-name"]', 'Tokyo Trip 2026');
    await page.fill('[data-testid="concept-prompt"]', 'Cinematic travel vlog with upbeat energy');

    // 3. Connect Google Drive folder
    await page.click('[data-testid="connect-drive"]');
    await page.click('[data-testid="folder-tokyo-trip"]');
    await page.click('[data-testid="confirm-folder"]');

    // 4. Start generation
    await page.click('[data-testid="generate-vlog"]');

    // 5. Wait for processing (with polling, max 5 min in staging)
    await expect(page.locator('[data-testid="status"]'))
      .toHaveText('Complete', { timeout: 300_000 });

    // 6. Verify output
    await expect(page.locator('[data-testid="video-player"]')).toBeVisible();
    await expect(page.locator('[data-testid="download-btn"]')).toBeEnabled();
  });
});
```

### Full E2E Scenario Matrix

| # | Scenario | Priority | Timeout |
|---|----------|----------|---------|
| 1 | Happy path: login → create → generate → download | P0 | 5 min |
| 2 | Auth failure: expired Google Drive token → re-auth prompt | P0 | 30s |
| 3 | Partial Veo 3 failure: 1 scene fails → automatic retry → success | P1 | 5 min |
| 4 | Large folder: 100+ files → pagination → correct file count | P1 | 2 min |
| 5 | Concept prompt validation: empty prompt → error message | P2 | 10s |
| 6 | Concurrent projects: 2 projects processing simultaneously | P2 | 8 min |
| 7 | Export profiles: switch between web-hd / social → correct output | P1 | 3 min |
| 8 | Cancel in-progress: cancel during Stage 3 → cleanup confirmed | P1 | 1 min |

### Playwright Configuration

```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 300_000,           // 5 min default for video processing
  retries: 1,                 // Retry flaky tests once
  workers: 2,                 // Parallel workers
  reporter: [
    ['html', { open: 'never' }],
    ['junit', { outputFile: 'results/e2e-junit.xml' }],
  ],
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:3000',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
});
```

---

## 4. Coverage Targets

| Module | Tool | Target | Enforcement |
|--------|------|--------|-------------|
| Backend API routes (TS) | Jest/Vitest | 80% | CI gate |
| Python synthesis scripts | pytest + coverage | 90% | CI gate |
| Frontend components | Vitest + Testing Library | 75% | CI gate |
| E2E user journeys | Playwright | 8 scenarios (all P0/P1 pass) | CI gate |

Coverage is enforced via CI — PRs with coverage below threshold are blocked:

```yaml
# In unit-tests job
- run: npm run test -- --coverage --coverageThreshold='{"global":{"lines":80}}'
- run: pytest tests/ --cov --cov-fail-under=80
```

---

## 5. Rollback Strategy

| Trigger | Action | Command |
|---------|--------|---------|
| Smoke test failure | Automatic rollback to previous revision | `gcloud run services update-traffic tripvlog-api --to-latest --region us-central1` (previous latest) |
| Error rate >5% (post-deploy) | Alert → manual rollback | `gcloud run services update-traffic tripvlog-api --to-revisions PREVIOUS_REV=100` |
| Canary latency spike | Hold at 10% → investigate | Monitor Cloud Run metrics dashboard |

Rollback is safe because Cloud Run retains previous revisions. No data migration is needed for stateless API services.
