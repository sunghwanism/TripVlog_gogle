import { Worker, Queue, Job } from 'bullmq'
import { pool } from '../db/client'
import { createRedisConnection } from './ingest.worker'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AnalyzeJobData {
  projectId: string
  userId: string
}

interface MediaFileRow {
  id: string
  drive_file_id: string
  file_name: string
  mime_type: string
  gcs_path: string | null
}

interface ExtractedMetadata {
  gps_lat?: number | null
  gps_lng?: number | null
  location_name?: string | null
  captured_at?: string | null
  camera_info?: string | null
  orientation?: number | null
  duration_ms?: number | null
  width?: number | null
  height?: number | null
  fps?: number | null
  codec?: string | null
}

interface MediaBatchPayload {
  projectId: string
  files: Array<{
    id: string
    gcsPath: string
    mimeType: string
  }>
}

interface AiServiceResponse {
  results: Array<{
    id: string
    metadata: ExtractedMetadata
  }>
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getAiServiceUrl(): string {
  const url = process.env.AI_SERVICE_URL
  if (!url) throw new Error('AI_SERVICE_URL not configured')
  return url
}

/**
 * Calls the Python AI microservice to extract metadata for a batch of files.
 * Retries once on failure. Returns new objects — never mutates the input.
 */
async function callAiService(payload: MediaBatchPayload): Promise<AiServiceResponse> {
  const url = `${getAiServiceUrl()}/analyze`

  const attempt = async (): Promise<AiServiceResponse> => {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      throw new Error(`AI service returned ${response.status}: ${response.statusText}`)
    }

    return response.json() as Promise<AiServiceResponse>
  }

  try {
    return await attempt()
  } catch (firstError) {
    console.warn('[analyze] AI service call failed, retrying once:', firstError)
    try {
      return await attempt()
    } catch (secondError) {
      throw new Error(
        `AI service unavailable after retry: ${(secondError as Error).message}`,
      )
    }
  }
}

// ─── Core analyze logic ───────────────────────────────────────────────────────

async function runAnalyzeJob(job: Job<AnalyzeJobData>): Promise<void> {
  const { projectId, userId } = job.data

  // 1. Mark job RUNNING
  await pool.query(
    `UPDATE generation_jobs
     SET status = 'RUNNING', started_at = NOW(), attempt_count = attempt_count + 1,
         worker_id = $1
     WHERE project_id = $2 AND phase = 'ANALYZE' AND status IN ('PENDING', 'RETRYING')`,
    [job.id, projectId],
  )

  // 2. Fetch all media_files not yet extracted (with a GCS path)
  const filesResult = await pool.query<MediaFileRow>(
    `SELECT id, drive_file_id, file_name, mime_type, gcs_path
     FROM media_files
     WHERE project_id = $1
       AND metadata_extracted = FALSE
       AND gcs_path IS NOT NULL
       AND skip_reason IS NULL`,
    [projectId],
  )

  const files = filesResult.rows

  if (files.length === 0) {
    // Nothing to analyze — complete immediately
    await finalizeAnalyzeJob(projectId, userId)
    return
  }

  // 3. Call AI service with the batch
  const payload: MediaBatchPayload = {
    projectId,
    files: files.map((f) => ({
      id: f.id,
      gcsPath: f.gcs_path!,
      mimeType: f.mime_type,
    })),
  }

  let aiResponse: AiServiceResponse

  try {
    aiResponse = await callAiService(payload)
  } catch (err) {
    // Log failure but continue — we'll mark all files with a skip
    console.error('[analyze] AI service failed:', err)
    await pool.query(
      `UPDATE generation_jobs
       SET status = 'FAILED', error_log = $1, completed_at = NOW()
       WHERE project_id = $2 AND phase = 'ANALYZE'`,
      [(err as Error).message, projectId],
    )
    await pool.query(
      `UPDATE projects SET status = 'FAILED', error_message = $1, updated_at = NOW()
       WHERE id = $2`,
      ['Metadata extraction failed', projectId],
    )
    return
  }

  // 4. Update each media_files row with returned metadata
  for (const result of aiResponse.results) {
    const { id, metadata } = result

    await pool.query(
      `UPDATE media_files SET
         gps_lat            = $1,
         gps_lng            = $2,
         location_name      = $3,
         captured_at        = $4,
         camera_info        = $5,
         orientation        = $6,
         duration_ms        = $7,
         width              = $8,
         height             = $9,
         fps                = $10,
         codec              = $11,
         metadata_extracted = TRUE
       WHERE id = $12`,
      [
        metadata.gps_lat ?? null,
        metadata.gps_lng ?? null,
        metadata.location_name ?? null,
        metadata.captured_at ?? null,
        metadata.camera_info ?? null,
        metadata.orientation ?? null,
        metadata.duration_ms ?? null,
        metadata.width ?? null,
        metadata.height ?? null,
        metadata.fps ?? null,
        metadata.codec ?? null,
        id,
      ],
    )
  }

  await finalizeAnalyzeJob(projectId, userId)
}

async function finalizeAnalyzeJob(projectId: string, userId: string): Promise<void> {
  // 5. Mark ANALYZE job COMPLETED
  await pool.query(
    `UPDATE generation_jobs
     SET status = 'COMPLETED', completed_at = NOW()
     WHERE project_id = $1 AND phase = 'ANALYZE'`,
    [projectId],
  )

  // 6. Insert PLAN job record and enqueue for Phase 02
  await pool.query(
    `INSERT INTO generation_jobs (project_id, phase, status)
     VALUES ($1, 'PLAN', 'PENDING')`,
    [projectId],
  )

  await pool.query(
    `UPDATE projects SET status = 'PLANNING', updated_at = NOW() WHERE id = $1`,
    [projectId],
  )

  const redis = createRedisConnection()
  const planQueue = new Queue('pipeline', { connection: redis })
  await planQueue.add('plan', { projectId, userId }, { attempts: 3 })
  await redis.quit()
}

// ─── Worker factory ───────────────────────────────────────────────────────────

export function startAnalyzeWorker(): Worker<AnalyzeJobData> {
  const worker = new Worker<AnalyzeJobData>(
    'pipeline',
    async (job) => {
      if (job.name !== 'analyze') return
      await runAnalyzeJob(job)
    },
    {
      connection: createRedisConnection(),
      concurrency: 3,
    },
  )

  worker.on('failed', async (job, err) => {
    if (!job) return
    const { projectId } = job.data
    console.error(`[analyze] job failed for project ${projectId}:`, err)

    if (job.attemptsMade >= (job.opts.attempts ?? 3)) {
      await pool.query(
        `UPDATE generation_jobs
         SET status = 'FAILED', error_log = $1, completed_at = NOW()
         WHERE project_id = $2 AND phase = 'ANALYZE'`,
        [err.message, projectId],
      )
      await pool.query(
        `UPDATE projects SET status = 'FAILED', error_message = $1, updated_at = NOW()
         WHERE id = $2`,
        ['Analysis failed after maximum retries', projectId],
      )
    }
  })

  return worker
}
