import { Router, Request, Response } from 'express'
import { Queue } from 'bullmq'
import IORedis from 'ioredis'
import { pool } from '../db/client'
import { requireAuth } from '../middleware/auth'
import {
  CreateProjectSchema,
  ProjectIdParamSchema,
  PaginationQuerySchema,
} from '../validation/schemas'

const router = Router()

// All project routes require authentication
router.use(requireAuth)

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getRedisUrl(): string {
  const url = process.env.REDIS_URL
  if (!url) throw new Error('REDIS_URL not configured')
  return url
}

function createRedis(): IORedis {
  return new IORedis(getRedisUrl(), { maxRetriesPerRequest: null })
}

// ─── POST /api/projects ───────────────────────────────────────────────────────

/**
 * Creates a new project and enqueues the INGEST phase job.
 * Returns the created project row.
 */
router.post('/', async (req: Request, res: Response) => {
  const parsed = CreateProjectSchema.safeParse(req.body)
  if (!parsed.success) {
    res.status(400).json({ error: 'Invalid request', details: parsed.error.flatten() })
    return
  }

  const { folder_id, concept_prompt } = parsed.data
  const userId = req.user!.id

  try {
    // Insert project row
    const projectResult = await pool.query<{ id: string; status: string; created_at: string }>(
      `INSERT INTO projects (user_id, folder_id, concept_prompt)
       VALUES ($1, $2, $3)
       RETURNING id, status, created_at`,
      [userId, folder_id, concept_prompt],
    )
    const project = projectResult.rows[0]

    // Insert INGEST generation_job record
    await pool.query(
      `INSERT INTO generation_jobs (project_id, phase, status)
       VALUES ($1, 'INGEST', 'PENDING')`,
      [project.id],
    )

    // Enqueue BullMQ ingest job
    const redis = createRedis()
    const queue = new Queue('pipeline', { connection: redis })
    await queue.add('ingest', { projectId: project.id, userId }, { attempts: 3 })
    await redis.quit()

    res.status(201).json({
      id: project.id,
      status: project.status,
      folderId: folder_id,
      conceptPrompt: concept_prompt,
      createdAt: project.created_at,
    })
  } catch (error) {
    console.error('[projects/create] error:', error)
    res.status(500).json({ error: 'Failed to create project' })
  }
})

// ─── GET /api/projects/:id ────────────────────────────────────────────────────

/**
 * Returns project status, file counts, and latest generation job info.
 */
router.get('/:id', async (req: Request, res: Response) => {
  const paramParsed = ProjectIdParamSchema.safeParse(req.params)
  if (!paramParsed.success) {
    res.status(400).json({ error: 'Invalid project ID' })
    return
  }

  const { id } = paramParsed.data
  const userId = req.user!.id

  try {
    const result = await pool.query<{
      id: string
      folder_id: string
      concept_prompt: string
      status: string
      total_files: number
      processed_files: number
      error_message: string | null
      created_at: string
      updated_at: string
    }>(
      `SELECT id, folder_id, concept_prompt, status, total_files,
              processed_files, error_message, created_at, updated_at
       FROM projects
       WHERE id = $1 AND user_id = $2`,
      [id, userId],
    )

    if (result.rows.length === 0) {
      res.status(404).json({ error: 'Project not found' })
      return
    }

    const project = result.rows[0]

    // Fetch latest generation job
    const jobResult = await pool.query<{
      phase: string
      status: string
      attempt_count: number
      started_at: string | null
      completed_at: string | null
    }>(
      `SELECT phase, status, attempt_count, started_at, completed_at
       FROM generation_jobs
       WHERE project_id = $1
       ORDER BY created_at DESC
       LIMIT 1`,
      [id],
    )

    res.json({
      id: project.id,
      folderId: project.folder_id,
      conceptPrompt: project.concept_prompt,
      status: project.status,
      totalFiles: project.total_files,
      processedFiles: project.processed_files,
      errorMessage: project.error_message,
      createdAt: project.created_at,
      updatedAt: project.updated_at,
      currentJob: jobResult.rows[0] ?? null,
    })
  } catch (error) {
    console.error('[projects/get] error:', error)
    res.status(500).json({ error: 'Failed to retrieve project' })
  }
})

// ─── GET /api/projects/:id/files ──────────────────────────────────────────────

/**
 * Returns a paginated list of media_files for the project.
 * Query params: page (default 1), limit (default 20, max 100)
 */
router.get('/:id/files', async (req: Request, res: Response) => {
  const paramParsed = ProjectIdParamSchema.safeParse(req.params)
  if (!paramParsed.success) {
    res.status(400).json({ error: 'Invalid project ID' })
    return
  }

  const queryParsed = PaginationQuerySchema.safeParse(req.query)
  if (!queryParsed.success) {
    res.status(400).json({ error: 'Invalid pagination params', details: queryParsed.error.flatten() })
    return
  }

  const { id } = paramParsed.data
  const { page, limit } = queryParsed.data
  const userId = req.user!.id
  const offset = (page - 1) * limit

  try {
    // Verify project ownership
    const ownerCheck = await pool.query(
      `SELECT 1 FROM projects WHERE id = $1 AND user_id = $2`,
      [id, userId],
    )
    if (ownerCheck.rows.length === 0) {
      res.status(404).json({ error: 'Project not found' })
      return
    }

    const filesResult = await pool.query<{
      id: string
      drive_file_id: string
      file_name: string
      mime_type: string
      file_size_bytes: string
      gcs_path: string | null
      gps_lat: number | null
      gps_lng: number | null
      location_name: string | null
      captured_at: string | null
      camera_info: string | null
      orientation: number | null
      duration_ms: number | null
      width: number | null
      height: number | null
      fps: number | null
      codec: string | null
      skip_reason: string | null
      metadata_extracted: boolean
      created_at: string
    }>(
      `SELECT id, drive_file_id, file_name, mime_type, file_size_bytes,
              gcs_path, gps_lat, gps_lng, location_name, captured_at,
              camera_info, orientation, duration_ms, width, height,
              fps, codec, skip_reason, metadata_extracted, created_at
       FROM media_files
       WHERE project_id = $1
       ORDER BY captured_at ASC NULLS LAST, created_at ASC
       LIMIT $2 OFFSET $3`,
      [id, limit, offset],
    )

    const countResult = await pool.query<{ count: string }>(
      `SELECT COUNT(*) AS count FROM media_files WHERE project_id = $1`,
      [id],
    )

    const total = parseInt(countResult.rows[0].count, 10)

    res.json({
      data: filesResult.rows.map((f) => ({
        id: f.id,
        driveFileId: f.drive_file_id,
        fileName: f.file_name,
        mimeType: f.mime_type,
        fileSizeBytes: Number(f.file_size_bytes),
        gcsPath: f.gcs_path,
        gpsLat: f.gps_lat,
        gpsLng: f.gps_lng,
        locationName: f.location_name,
        capturedAt: f.captured_at,
        cameraInfo: f.camera_info,
        orientation: f.orientation,
        durationMs: f.duration_ms,
        width: f.width,
        height: f.height,
        fps: f.fps,
        codec: f.codec,
        skipReason: f.skip_reason,
        metadataExtracted: f.metadata_extracted,
        createdAt: f.created_at,
      })),
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
      },
    })
  } catch (error) {
    console.error('[projects/files] error:', error)
    res.status(500).json({ error: 'Failed to retrieve files' })
  }
})

// ─── GET /api/projects/:id/progress (SSE) ────────────────────────────────────

/**
 * Server-Sent Events endpoint — subscribes to Redis pub/sub channel
 * `project:{id}:progress` and streams progress events to the client.
 *
 * The client receives JSON lines in the SSE `data:` field.
 * Connection stays open until the client disconnects.
 */
router.get('/:id/progress', async (req: Request, res: Response) => {
  const paramParsed = ProjectIdParamSchema.safeParse(req.params)
  if (!paramParsed.success) {
    res.status(400).json({ error: 'Invalid project ID' })
    return
  }

  const { id } = paramParsed.data
  const userId = req.user!.id

  // Verify project ownership before opening SSE channel
  try {
    const ownerCheck = await pool.query(
      `SELECT 1 FROM projects WHERE id = $1 AND user_id = $2`,
      [id, userId],
    )
    if (ownerCheck.rows.length === 0) {
      res.status(404).json({ error: 'Project not found' })
      return
    }
  } catch (error) {
    console.error('[projects/progress] ownership check error:', error)
    res.status(500).json({ error: 'Failed to verify project' })
    return
  }

  // Set SSE headers
  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection', 'keep-alive')
  res.setHeader('X-Accel-Buffering', 'no') // Disable nginx buffering
  res.flushHeaders()

  // Send initial heartbeat
  res.write('data: {"type":"connected"}\n\n')

  const redis = createRedis()
  const channel = `project:${id}:progress`

  await redis.subscribe(channel)

  redis.on('message', (_ch: string, message: string) => {
    res.write(`data: ${message}\n\n`)
  })

  // Heartbeat every 30s to keep the connection alive
  const heartbeat = setInterval(() => {
    res.write('data: {"type":"heartbeat"}\n\n')
  }, 30_000)

  req.on('close', async () => {
    clearInterval(heartbeat)
    await redis.unsubscribe(channel)
    redis.quit()
  })
})

export default router
