/**
 * Projects routes tests — mocks pg pool and BullMQ.
 */
import express from 'express'
import cookieParser from 'cookie-parser'
import request from 'supertest'
import jwt from 'jsonwebtoken'

// ─── Mocks ────────────────────────────────────────────────────────────────────

jest.mock('../src/db/client', () => ({
  pool: { query: jest.fn() },
}))

jest.mock('bullmq', () => ({
  Queue: jest.fn().mockImplementation(() => ({
    add: jest.fn().mockResolvedValue({}),
  })),
  Worker: jest.fn(),
}))

jest.mock('ioredis', () =>
  jest.fn().mockImplementation(() => ({
    subscribe: jest.fn(),
    unsubscribe: jest.fn(),
    quit: jest.fn(),
    on: jest.fn(),
    publish: jest.fn(),
  })),
)

// ─── Setup ────────────────────────────────────────────────────────────────────

const TEST_JWT_SECRET = 'test-jwt-secret'
const TEST_USER_ID = '550e8400-e29b-41d4-a716-446655440000'
const TEST_PROJECT_ID = '660e8400-e29b-41d4-a716-446655440001'

beforeEach(() => {
  process.env.JWT_SECRET = TEST_JWT_SECRET
  process.env.REDIS_URL = 'redis://localhost:6379'
})

afterEach(() => {
  jest.clearAllMocks()
  delete process.env.JWT_SECRET
  delete process.env.REDIS_URL
})

function makeSessionCookie() {
  const token = jwt.sign(
    { id: TEST_USER_ID, email: 'user@example.com', googleId: 'gid' },
    TEST_JWT_SECRET,
  )
  return `session=${token}`
}

function buildApp() {
  const app = express()
  app.use(express.json())
  app.use(cookieParser())
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const projectsRouter = require('../src/routes/projects').default
  app.use('/api/projects', projectsRouter)
  return app
}

// ─── POST /api/projects ───────────────────────────────────────────────────────

describe('POST /api/projects', () => {
  it('returns 401 without auth cookie', async () => {
    const app = buildApp()
    const res = await request(app).post('/api/projects').send({
      folder_id: 'abc123',
      concept_prompt: 'A cinematic road trip',
    })
    expect(res.status).toBe(401)
  })

  it('returns 400 for invalid input (short concept_prompt)', async () => {
    const app = buildApp()
    const res = await request(app)
      .post('/api/projects')
      .set('Cookie', makeSessionCookie())
      .send({ folder_id: 'abc123', concept_prompt: 'short' })
    expect(res.status).toBe(400)
    expect(res.body.error).toBe('Invalid request')
  })

  it('returns 400 for missing folder_id', async () => {
    const app = buildApp()
    const res = await request(app)
      .post('/api/projects')
      .set('Cookie', makeSessionCookie())
      .send({ concept_prompt: 'A cinematic summer road trip through Japan' })
    expect(res.status).toBe(400)
  })

  it('creates project and returns 201 with project data', async () => {
    const { pool } = require('../src/db/client')
    pool.query
      .mockResolvedValueOnce({
        rows: [{
          id: TEST_PROJECT_ID,
          status: 'CREATED',
          created_at: '2026-03-22T00:00:00Z',
        }],
      })
      .mockResolvedValueOnce({ rows: [] }) // generation_jobs insert

    const app = buildApp()
    const res = await request(app)
      .post('/api/projects')
      .set('Cookie', makeSessionCookie())
      .send({
        folder_id: 'drive-folder-abc',
        concept_prompt: 'A cinematic summer road trip through coastal Japan',
      })

    expect(res.status).toBe(201)
    expect(res.body.id).toBe(TEST_PROJECT_ID)
    expect(res.body.status).toBe('CREATED')
    expect(res.body.folderId).toBe('drive-folder-abc')
  })
})

// ─── GET /api/projects/:id ────────────────────────────────────────────────────

describe('GET /api/projects/:id', () => {
  it('returns 400 for non-UUID project ID', async () => {
    const app = buildApp()
    const res = await request(app)
      .get('/api/projects/not-a-uuid')
      .set('Cookie', makeSessionCookie())
    expect(res.status).toBe(400)
  })

  it('returns 404 when project not found or not owned by user', async () => {
    const { pool } = require('../src/db/client')
    pool.query.mockResolvedValue({ rows: [] })

    const app = buildApp()
    const res = await request(app)
      .get(`/api/projects/${TEST_PROJECT_ID}`)
      .set('Cookie', makeSessionCookie())
    expect(res.status).toBe(404)
  })

  it('returns project with status and file counts', async () => {
    const { pool } = require('../src/db/client')
    pool.query
      .mockResolvedValueOnce({
        rows: [{
          id: TEST_PROJECT_ID,
          folder_id: 'drive-folder-abc',
          concept_prompt: 'Road trip',
          status: 'INGESTING',
          total_files: 10,
          processed_files: 3,
          error_message: null,
          created_at: '2026-03-22T00:00:00Z',
          updated_at: '2026-03-22T01:00:00Z',
        }],
      })
      .mockResolvedValueOnce({
        rows: [{
          phase: 'INGEST',
          status: 'RUNNING',
          attempt_count: 1,
          started_at: '2026-03-22T00:30:00Z',
          completed_at: null,
        }],
      })

    const app = buildApp()
    const res = await request(app)
      .get(`/api/projects/${TEST_PROJECT_ID}`)
      .set('Cookie', makeSessionCookie())

    expect(res.status).toBe(200)
    expect(res.body.id).toBe(TEST_PROJECT_ID)
    expect(res.body.status).toBe('INGESTING')
    expect(res.body.totalFiles).toBe(10)
    expect(res.body.processedFiles).toBe(3)
    expect(res.body.currentJob.phase).toBe('INGEST')
  })
})

// ─── GET /api/projects/:id/files ──────────────────────────────────────────────

describe('GET /api/projects/:id/files', () => {
  it('returns paginated file list', async () => {
    const { pool } = require('../src/db/client')
    pool.query
      .mockResolvedValueOnce({ rows: [{ '?column?': 1 }] }) // ownership check
      .mockResolvedValueOnce({
        rows: [{
          id: 'file-uuid-1',
          drive_file_id: 'gdrive-1',
          file_name: 'photo.jpg',
          mime_type: 'image/jpeg',
          file_size_bytes: '2048000',
          gcs_path: 'projects/proj/file1/photo.jpg',
          gps_lat: 37.5665,
          gps_lng: 126.978,
          location_name: 'Seoul, South Korea',
          captured_at: '2026-03-10T08:30:00Z',
          camera_info: 'Apple iPhone 16 Pro',
          orientation: 1,
          duration_ms: null,
          width: 4032,
          height: 3024,
          fps: null,
          codec: null,
          skip_reason: null,
          metadata_extracted: true,
          created_at: '2026-03-22T00:00:00Z',
        }],
      })
      .mockResolvedValueOnce({ rows: [{ count: '1' }] })

    const app = buildApp()
    const res = await request(app)
      .get(`/api/projects/${TEST_PROJECT_ID}/files`)
      .set('Cookie', makeSessionCookie())

    expect(res.status).toBe(200)
    expect(res.body.data).toHaveLength(1)
    expect(res.body.data[0].fileName).toBe('photo.jpg')
    expect(res.body.data[0].locationName).toBe('Seoul, South Korea')
    expect(res.body.pagination.total).toBe(1)
    expect(res.body.pagination.page).toBe(1)
  })

  it('applies pagination params', async () => {
    const { pool } = require('../src/db/client')
    pool.query
      .mockResolvedValueOnce({ rows: [{ '?column?': 1 }] })
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [{ count: '50' }] })

    const app = buildApp()
    const res = await request(app)
      .get(`/api/projects/${TEST_PROJECT_ID}/files?page=2&limit=10`)
      .set('Cookie', makeSessionCookie())

    expect(res.status).toBe(200)
    expect(res.body.pagination.page).toBe(2)
    expect(res.body.pagination.limit).toBe(10)
    expect(res.body.pagination.totalPages).toBe(5)
  })
})
