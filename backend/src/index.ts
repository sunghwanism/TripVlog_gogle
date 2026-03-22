import express from 'express'
import cookieParser from 'cookie-parser'
import cors from 'cors'
import authRouter from './routes/auth'
import projectsRouter from './routes/projects'
import { startIngestWorker } from './workers/ingest.worker'
import { startAnalyzeWorker } from './workers/analyze.worker'

// ─── Validate required env vars on startup ────────────────────────────────────

const REQUIRED_ENV_VARS = [
  'DATABASE_URL',
  'REDIS_URL',
  'GOOGLE_CLIENT_ID',
  'GOOGLE_CLIENT_SECRET',
  'GOOGLE_REDIRECT_URI',
  'TOKEN_ENCRYPTION_KEY',
  'JWT_SECRET',
] as const

for (const key of REQUIRED_ENV_VARS) {
  if (!process.env[key]) {
    throw new Error(`${key} not configured`)
  }
}

// ─── Express app ──────────────────────────────────────────────────────────────

const app = express()

app.use(
  cors({
    origin: process.env.CORS_ORIGIN ?? 'http://localhost:3000',
    credentials: true,
  }),
)
app.use(express.json())
app.use(cookieParser())

// ─── Routes ───────────────────────────────────────────────────────────────────

app.use('/api/auth', authRouter)
app.use('/api/projects', projectsRouter)

// Health check (no auth required)
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', ts: new Date().toISOString() })
})

// 404 handler
app.use((_req, res) => {
  res.status(404).json({ error: 'Not found' })
})

// Generic error handler — never leaks stack traces to the client
app.use((err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  console.error('[unhandled error]', err)
  res.status(500).json({ error: 'Internal server error' })
})

// ─── Start workers ────────────────────────────────────────────────────────────

startIngestWorker()
startAnalyzeWorker()

// ─── Listen ───────────────────────────────────────────────────────────────────

const PORT = parseInt(process.env.PORT ?? '3001', 10)

app.listen(PORT, () => {
  console.log(`[server] listening on port ${PORT}`)
})

export default app
