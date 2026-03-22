/**
 * Auth routes tests — mocks googleapis and pg pool.
 */
import express from 'express'
import cookieParser from 'cookie-parser'
import request from 'supertest'
import jwt from 'jsonwebtoken'

// ─── Mocks ────────────────────────────────────────────────────────────────────

jest.mock('googleapis', () => {
  const getToken = jest.fn()
  const userinfoGet = jest.fn()
  const OAuth2 = jest.fn().mockImplementation(() => ({
    getToken,
    setCredentials: jest.fn(),
    on: jest.fn(),
  }))

  return {
    google: {
      auth: { OAuth2 },
      oauth2: jest.fn().mockReturnValue({
        userinfo: { get: userinfoGet },
      }),
    },
    _mocks: { getToken, userinfoGet },
  }
})

jest.mock('../src/db/client', () => ({
  pool: { query: jest.fn() },
}))

jest.mock('../src/services/encryption', () => ({
  encrypt: jest.fn().mockReturnValue(Buffer.from('encrypted')),
  decrypt: jest.fn().mockReturnValue('decrypted-token'),
}))

// ─── Setup ────────────────────────────────────────────────────────────────────

const TEST_JWT_SECRET = 'test-jwt-secret-value'

beforeEach(() => {
  process.env.GOOGLE_CLIENT_ID = 'test-client-id'
  process.env.GOOGLE_CLIENT_SECRET = 'test-client-secret'
  process.env.GOOGLE_REDIRECT_URI = 'http://localhost:3001/api/auth/google/callback'
  process.env.JWT_SECRET = TEST_JWT_SECRET
  process.env.TOKEN_ENCRYPTION_KEY = 'a'.repeat(64)
})

afterEach(() => {
  jest.clearAllMocks()
  delete process.env.GOOGLE_CLIENT_ID
  delete process.env.GOOGLE_CLIENT_SECRET
  delete process.env.GOOGLE_REDIRECT_URI
  delete process.env.JWT_SECRET
  delete process.env.TOKEN_ENCRYPTION_KEY
})

function buildApp() {
  const app = express()
  app.use(express.json())
  app.use(cookieParser())
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const authRouter = require('../src/routes/auth').default
  app.use('/api/auth', authRouter)
  return app
}

// ─── POST /api/auth/google/callback ──────────────────────────────────────────

describe('POST /api/auth/google/callback', () => {
  it('returns 400 when code is missing', async () => {
    const app = buildApp()
    const res = await request(app).post('/api/auth/google/callback').send({})
    expect(res.status).toBe(400)
    expect(res.body.error).toBe('Invalid request')
  })

  it('returns 400 when code is empty string', async () => {
    const app = buildApp()
    const res = await request(app).post('/api/auth/google/callback').send({ code: '' })
    expect(res.status).toBe(400)
  })

  it('sets httpOnly session cookie on success', async () => {
    const { google, _mocks } = require('googleapis') as ReturnType<typeof jest.fn> & {
      google: typeof import('googleapis').google
      _mocks: { getToken: jest.Mock; userinfoGet: jest.Mock }
    }

    _mocks.getToken.mockResolvedValue({
      tokens: {
        access_token: 'access-token',
        refresh_token: 'refresh-token',
        expiry_date: Date.now() + 3600_000,
      },
    })

    _mocks.userinfoGet.mockResolvedValue({
      data: { id: 'google-user-123', email: 'user@example.com', name: 'Test User' },
    })

    const { pool } = require('../src/db/client')
    pool.query.mockResolvedValue({
      rows: [{ id: 'db-user-uuid', email: 'user@example.com', google_id: 'google-user-123' }],
    })

    const app = buildApp()
    const res = await request(app)
      .post('/api/auth/google/callback')
      .send({ code: 'valid-auth-code' })

    expect(res.status).toBe(200)
    expect(res.body).toEqual({ ok: true })

    const cookies = res.headers['set-cookie'] as string[] | string
    const cookieStr = Array.isArray(cookies) ? cookies.join('; ') : cookies
    expect(cookieStr).toMatch(/session=/)
    expect(cookieStr).toMatch(/HttpOnly/i)
    expect(cookieStr).toMatch(/SameSite=Strict/i)
  })

  it('returns 500 without leaking error details when Google API fails', async () => {
    const { _mocks } = require('googleapis') as { _mocks: { getToken: jest.Mock } }
    _mocks.getToken.mockRejectedValue(new Error('Google API down'))

    const app = buildApp()
    const res = await request(app)
      .post('/api/auth/google/callback')
      .send({ code: 'bad-code' })

    expect(res.status).toBe(500)
    expect(res.body.error).toBe('Authentication failed')
    // Must not leak internal error message
    expect(JSON.stringify(res.body)).not.toMatch(/Google API down/)
  })
})

// ─── GET /api/auth/me ─────────────────────────────────────────────────────────

describe('GET /api/auth/me', () => {
  it('returns 401 when no session cookie is present', async () => {
    const app = buildApp()
    const res = await request(app).get('/api/auth/me')
    expect(res.status).toBe(401)
  })

  it('returns 401 for an invalid JWT', async () => {
    const app = buildApp()
    const res = await request(app)
      .get('/api/auth/me')
      .set('Cookie', 'session=invalid.jwt.token')
    expect(res.status).toBe(401)
  })

  it('returns user profile for a valid JWT', async () => {
    const token = jwt.sign(
      { id: 'user-uuid', email: 'user@example.com', googleId: 'gid-123' },
      TEST_JWT_SECRET,
    )

    const { pool } = require('../src/db/client')
    pool.query.mockResolvedValue({
      rows: [{
        id: 'user-uuid',
        email: 'user@example.com',
        display_name: 'Test User',
        google_id: 'gid-123',
        created_at: '2026-01-01T00:00:00Z',
      }],
    })

    const app = buildApp()
    const res = await request(app)
      .get('/api/auth/me')
      .set('Cookie', `session=${token}`)

    expect(res.status).toBe(200)
    expect(res.body.id).toBe('user-uuid')
    expect(res.body.email).toBe('user@example.com')
    expect(res.body.displayName).toBe('Test User')
    // Ensure no token fields in response
    expect(res.body.accessToken).toBeUndefined()
    expect(res.body.refreshToken).toBeUndefined()
  })

  it('returns 404 when user is not found in DB', async () => {
    const token = jwt.sign(
      { id: 'nonexistent-uuid', email: 'x@example.com', googleId: 'gid' },
      TEST_JWT_SECRET,
    )

    const { pool } = require('../src/db/client')
    pool.query.mockResolvedValue({ rows: [] })

    const app = buildApp()
    const res = await request(app)
      .get('/api/auth/me')
      .set('Cookie', `session=${token}`)

    expect(res.status).toBe(404)
  })
})
