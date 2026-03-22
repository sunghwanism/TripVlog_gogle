import { google, drive_v3 } from 'googleapis'
import { pool } from '../db/client'
import { encrypt } from './encryption'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface DriveFile {
  id: string
  name: string
  mimeType: string
  size: number
  createdTime: string
  imageMediaMetadata?: drive_v3.Schema$File['imageMediaMetadata']
  videoMediaMetadata?: drive_v3.Schema$File['videoMediaMetadata']
}

export class SkipFileError extends Error {
  constructor(
    public readonly reason: string,
    message?: string,
  ) {
    super(message ?? reason)
    this.name = 'SkipFileError'
  }
}

// ─── Supported MIME types for ingestion ───────────────────────────────────────

const SUPPORTED_MIME_TYPES = new Set([
  'image/jpeg',
  'image/png',
  'image/heic',
  'video/mp4',
  'video/quicktime',
])

const MAX_FILE_BYTES_CHUNKED = 500 * 1024 * 1024   // 500 MB — skip above this
const THRESHOLD_CHUNKED_BYTES = 50 * 1024 * 1024   // 50 MB — chunk above this
const CHUNK_SIZE_BYTES = 8 * 1024 * 1024            // 8 MB per chunk

// ─── OAuth2 client factory ────────────────────────────────────────────────────

function getOAuthClientBase() {
  const clientId = process.env.GOOGLE_CLIENT_ID
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET
  const redirectUri = process.env.GOOGLE_REDIRECT_URI

  if (!clientId) throw new Error('GOOGLE_CLIENT_ID not configured')
  if (!clientSecret) throw new Error('GOOGLE_CLIENT_SECRET not configured')
  if (!redirectUri) throw new Error('GOOGLE_REDIRECT_URI not configured')

  return new google.auth.OAuth2(clientId, clientSecret, redirectUri)
}

/**
 * Creates an authenticated Google Drive client.
 * Registers a token-refresh listener that re-encrypts and persists new tokens.
 *
 * @param accessToken  Decrypted access token string
 * @param refreshToken Decrypted refresh token string
 * @param userId       DB user ID (UUID) for persisting refreshed tokens
 */
export function createDriveClient(
  accessToken: string,
  refreshToken: string,
  userId: string,
): drive_v3.Drive {
  const oauth2Client = getOAuthClientBase()

  oauth2Client.setCredentials({
    access_token: accessToken,
    refresh_token: refreshToken,
  })

  // Auto-persist newly refreshed tokens back to DB (re-encrypted)
  oauth2Client.on('tokens', async (newTokens) => {
    try {
      if (!newTokens.access_token) return

      const encryptedAccess = encrypt(newTokens.access_token)
      const expiresAt = newTokens.expiry_date
        ? new Date(newTokens.expiry_date).toISOString()
        : null

      await pool.query(
        `UPDATE users
         SET access_token_enc  = $1,
             token_expires_at  = COALESCE($2::TIMESTAMPTZ, token_expires_at),
             updated_at        = NOW()
         WHERE id = $3`,
        [encryptedAccess, expiresAt, userId],
      )
    } catch (err) {
      console.error('[drive] failed to persist refreshed token:', err)
    }
  })

  return google.drive({ version: 'v3', auth: oauth2Client })
}

// ─── File enumeration ─────────────────────────────────────────────────────────

/**
 * Async generator that paginates through all supported media files in a Drive folder.
 * Yields batches of DriveFile objects in createdTime order (ascending).
 *
 * Uses nextPageToken to avoid loading the full list into memory.
 */
export async function* listFiles(
  drive: drive_v3.Drive,
  folderId: string,
): AsyncGenerator<DriveFile[]> {
  let pageToken: string | undefined

  do {
    const response = await drive.files.list({
      q: `'${folderId}' in parents and trashed = false`,
      fields:
        'nextPageToken, files(id,name,mimeType,size,createdTime,imageMediaMetadata,videoMediaMetadata)',
      pageSize: 100,
      orderBy: 'createdTime',
      ...(pageToken ? { pageToken } : {}),
    })

    const files = response.data.files ?? []

    const filtered: DriveFile[] = files
      .filter((f) => f.id && f.name && f.mimeType && SUPPORTED_MIME_TYPES.has(f.mimeType))
      .map((f) => ({
        id: f.id!,
        name: f.name!,
        mimeType: f.mimeType!,
        size: Number(f.size ?? 0),
        createdTime: f.createdTime ?? new Date().toISOString(),
        imageMediaMetadata: f.imageMediaMetadata ?? undefined,
        videoMediaMetadata: f.videoMediaMetadata ?? undefined,
      }))

    if (filtered.length > 0) {
      yield filtered
    }

    pageToken = response.data.nextPageToken ?? undefined
  } while (pageToken)
}

// ─── File download ────────────────────────────────────────────────────────────

/**
 * Returns a readable stream for the given Drive file.
 *
 * Strategy by file size:
 *  - < 50 MB : direct media stream
 *  - 50–500 MB : chunked 8 MB range-request stream (resumable)
 *  - > 500 MB : throws SkipFileError — file is too large
 *
 * Never mutates the DriveFile argument.
 */
export async function downloadFile(
  drive: drive_v3.Drive,
  fileId: string,
  fileSizeBytes: number,
): Promise<NodeJS.ReadableStream> {
  if (fileSizeBytes > MAX_FILE_BYTES_CHUNKED) {
    throw new SkipFileError(
      `File exceeds 500 MB limit (${Math.round(fileSizeBytes / 1024 / 1024)} MB)`,
    )
  }

  if (fileSizeBytes >= THRESHOLD_CHUNKED_BYTES) {
    return downloadChunked(drive, fileId, fileSizeBytes)
  }

  // Direct stream for files < 50 MB
  const response = await drive.files.get(
    { fileId, alt: 'media' },
    { responseType: 'stream' },
  )
  return response.data as unknown as NodeJS.ReadableStream
}

/**
 * Downloads a file in 8 MB chunks and concatenates them into a PassThrough stream.
 * Supports implicit resume — each chunk is a separate HTTP range request.
 */
async function downloadChunked(
  drive: drive_v3.Drive,
  fileId: string,
  fileSizeBytes: number,
): Promise<NodeJS.ReadableStream> {
  const { PassThrough } = await import('stream')
  const output = new PassThrough()

  // Run chunked download in background, piping into the PassThrough
  ;(async () => {
    let offset = 0

    while (offset < fileSizeBytes) {
      const end = Math.min(offset + CHUNK_SIZE_BYTES - 1, fileSizeBytes - 1)

      try {
        const chunk = await drive.files.get(
          { fileId, alt: 'media' },
          {
            responseType: 'stream',
            headers: { Range: `bytes=${offset}-${end}` },
          },
        )

        await new Promise<void>((resolve, reject) => {
          const readable = chunk.data as unknown as NodeJS.ReadableStream
          readable.on('data', (data: Buffer) => output.write(data))
          readable.on('end', resolve)
          readable.on('error', reject)
        })
      } catch (err) {
        output.destroy(err instanceof Error ? err : new Error(String(err)))
        return
      }

      offset = end + 1
    }

    output.end()
  })()

  return output
}
