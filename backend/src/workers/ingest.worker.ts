import { Worker, Queue, Job } from 'bullmq'
import IORedis from 'ioredis'
import { pool } from '../db/client'
import { decrypt } from '../services/encryption'
import { createDriveClient, listFiles, downloadFile, SkipFileError } from '../services/drive'
import { uploadStream } from '../services/storage'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface IngestJobData {
  projectId: string
  userId: string
}

interface DbUser {
  access_token_enc: Buffer
  refresh_token_enc: Buffer
}

// ─── Redis connection ─────────────────────────────────────────────────────────

function getRedisUrl(): string {
  const url = process.env.REDIS_URL
  if (!url) throw new Error('REDIS_URL not configured')
  return url
}

export function createRedisConnection(): IORedis {
  return new IORedis(getRedisUrl(), { maxRetriesPerRequest: null })
}

// ─── Semaphore (max 3 concurrent downloads per project) ──────────────────────

class Semaphore {
  private queue: Array<() => void> = []
  private active = 0

  constructor(private readonly max: number) {}

  async acquire(): Promise<void> {
    if (this.active < this.max) {
      this.active++
      return
    }
    await new Promise<void>((resolve) => {
      this.queue.push(resolve)
    })
    this.active++
  }

  release(): void {
    this.active--
    const next = this.queue.shift()
    if (next) next()
  }
}

// ─── Retry helper (exponential backoff for Drive 429/5xx) ─────────────────────

async function withDriveRetry<T>(fn: () => Promise<T>, maxAttempts = 3): Promise<T> {
  let lastError: unknown

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      return await fn()
    } catch (err: unknown) {
      lastError = err
      const status = (err as { code?: number })?.code
      const isRetryable = status === 429 || (status !== undefined && status >= 500)

      if (!isRetryable || attempt === maxAttempts - 1) {
        throw err
      }

      const delayMs = 1000 * Math.pow(2, attempt)
      await sleep(delayMs)
    }
  }

  throw lastError
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// ─── Progress publisher ───────────────────────────────────────────────────────

async function publishProgress(
  redis: IORedis,
  projectId: string,
  payload: Record<string, unknown>,
): Promise<void> {
  await redis.publish(`project:${projectId}:progress`, JSON.stringify(payload))
}

// ─── Core ingest logic ────────────────────────────────────────────────────────

async function runIngestJob(job: Job<IngestJobData>, redis: IORedis): Promise<void> {
  const { projectId, userId } = job.data

  // 1. Mark job as RUNNING
  await pool.query(
    `UPDATE generation_jobs
     SET status = 'RUNNING', started_at = NOW(), attempt_count = attempt_count + 1,
         worker_id = $1
     WHERE project_id = $2 AND phase = 'INGEST' AND status IN ('PENDING', 'RETRYING')`,
    [job.id, projectId],
  )

  // 2. Load encrypted tokens from DB
  const userResult = await pool.query<DbUser>(
    `SELECT access_token_enc, refresh_token_enc FROM users WHERE id = $1`,
    [userId],
  )

  if (userResult.rows.length === 0) {
    throw new Error(`User not found: ${userId}`)
  }

  const { access_token_enc, refresh_token_enc } = userResult.rows[0]
  const accessToken = decrypt(access_token_enc)
  const refreshToken = decrypt(refresh_token_enc)

  // 3. Build Drive client
  const drive = createDriveClient(accessToken, refreshToken, userId)

  // 4. Fetch project to get folder_id
  const projectResult = await pool.query<{ folder_id: string }>(
    `SELECT folder_id FROM projects WHERE id = $1`,
    [projectId],
  )

  if (projectResult.rows.length === 0) {
    throw new Error(`Project not found: ${projectId}`)
  }

  const { folder_id } = projectResult.rows[0]

  await pool.query(
    `UPDATE projects SET status = 'INGESTING', updated_at = NOW() WHERE id = $1`,
    [projectId],
  )

  // 5. Enumerate files and count total
  const allFiles: Array<{
    id: string
    name: string
    mimeType: string
    size: number
    createdTime: string
  }> = []

  for await (const batch of listFiles(drive, folder_id)) {
    allFiles.push(...batch)
  }

  await pool.query(
    `UPDATE projects SET total_files = $1, updated_at = NOW() WHERE id = $2`,
    [allFiles.length, projectId],
  )

  // 6. Insert all media_files rows (pending download)
  for (const file of allFiles) {
    await pool.query(
      `INSERT INTO media_files
         (project_id, drive_file_id, file_name, mime_type, file_size_bytes)
       VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT DO NOTHING`,
      [projectId, file.id, file.name, file.mimeType, file.size],
    )
  }

  // 7. Download each file (max 3 concurrent) and upload to GCS
  const semaphore = new Semaphore(3)
  let processedCount = 0

  const downloadTasks = allFiles.map((file) =>
    (async () => {
      await semaphore.acquire()
      try {
        const gcsPath = `projects/${projectId}/${file.id}/${file.name}`

        let skipReason: string | null = null

        try {
          const stream = await withDriveRetry(() =>
            downloadFile(drive, file.id, file.size),
          )
          await uploadStream(stream, gcsPath)

          await pool.query(
            `UPDATE media_files
             SET gcs_path = $1
             WHERE project_id = $2 AND drive_file_id = $3`,
            [gcsPath, projectId, file.id],
          )
        } catch (err) {
          if (err instanceof SkipFileError) {
            skipReason = err.reason
          } else {
            skipReason = 'Download failed'
            console.error(`[ingest] download error for ${file.id}:`, err)
          }

          if (skipReason) {
            await pool.query(
              `UPDATE media_files
               SET skip_reason = $1
               WHERE project_id = $2 AND drive_file_id = $3`,
              [skipReason, projectId, file.id],
            )
          }
        }

        // 8. Increment processed count and publish progress
        processedCount++
        await pool.query(
          `UPDATE projects
           SET processed_files = $1, updated_at = NOW()
           WHERE id = $2`,
          [processedCount, projectId],
        )

        await publishProgress(redis, projectId, {
          phase: 'INGEST',
          processedFiles: processedCount,
          totalFiles: allFiles.length,
          fileName: file.name,
          skipped: skipReason !== null,
          skipReason,
        })
      } finally {
        semaphore.release()
      }
    })(),
  )

  await Promise.all(downloadTasks)

  // 9. Mark INGEST job COMPLETED
  await pool.query(
    `UPDATE generation_jobs
     SET status = 'COMPLETED', completed_at = NOW()
     WHERE project_id = $1 AND phase = 'INGEST'`,
    [projectId],
  )

  // 10. Enqueue ANALYZE job
  const analyzeQueue = new Queue('pipeline', { connection: redis })
  await analyzeQueue.add('analyze', { projectId, userId }, { attempts: 3 })

  await pool.query(
    `INSERT INTO generation_jobs (project_id, phase, status)
     VALUES ($1, 'ANALYZE', 'PENDING')`,
    [projectId],
  )

  await pool.query(
    `UPDATE projects SET status = 'ANALYZING', updated_at = NOW() WHERE id = $1`,
    [projectId],
  )
}

// ─── Worker factory ───────────────────────────────────────────────────────────

export function startIngestWorker(): Worker<IngestJobData> {
  const redis = createRedisConnection()

  const worker = new Worker<IngestJobData>(
    'pipeline',
    async (job) => {
      if (job.name !== 'ingest') return
      await runIngestJob(job, redis)
    },
    {
      connection: createRedisConnection(),
      concurrency: 5,
    },
  )

  worker.on('failed', async (job, err) => {
    if (!job) return
    const { projectId } = job.data
    console.error(`[ingest] job failed for project ${projectId}:`, err)

    if (job.attemptsMade >= (job.opts.attempts ?? 3)) {
      // Dead-letter: mark FAILED
      await pool.query(
        `UPDATE generation_jobs
         SET status = 'FAILED', error_log = $1, completed_at = NOW()
         WHERE project_id = $2 AND phase = 'INGEST'`,
        [err.message, projectId],
      )
      await pool.query(
        `UPDATE projects SET status = 'FAILED', error_message = $1, updated_at = NOW()
         WHERE id = $2`,
        ['Ingestion failed after maximum retries', projectId],
      )
      await redis.publish(
        `project:${projectId}:progress`,
        JSON.stringify({ phase: 'INGEST', status: 'FAILED', error: 'Ingestion failed' }),
      )
    }
  })

  return worker
}
