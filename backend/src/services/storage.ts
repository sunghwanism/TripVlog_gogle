import { Storage } from '@google-cloud/storage'

// GCS client authenticates via Application Default Credentials (ADC)
// Run `gcloud auth application-default login` locally, or use Workload Identity on GCP.
const storage = new Storage()

function getBucketName(): string {
  const bucket = process.env.GCS_BUCKET_NAME
  if (!bucket) throw new Error('GCS_BUCKET_NAME not configured')
  return bucket
}

/**
 * Uploads a readable stream to GCS at the given path.
 *
 * Returns the full GCS path (gs://bucket/path) on success.
 * Never mutates the input stream.
 *
 * @param readStream  A readable stream of file bytes
 * @param gcsPath     Destination path within the bucket (e.g. "projects/uuid/filename.mp4")
 */
export async function uploadStream(
  readStream: NodeJS.ReadableStream,
  gcsPath: string,
): Promise<string> {
  const bucketName = getBucketName()
  const bucket = storage.bucket(bucketName)
  const file = bucket.file(gcsPath)

  const writeStream = file.createWriteStream({
    resumable: false, // stream-based — let the caller handle chunking
    metadata: {
      cacheControl: 'private, no-cache',
    },
  })

  await new Promise<void>((resolve, reject) => {
    readStream.pipe(writeStream)
    writeStream.on('finish', resolve)
    writeStream.on('error', (err) => reject(new Error(`GCS upload failed: ${err.message}`)))
    readStream.on('error', (err) => reject(new Error(`Read stream error: ${err.message}`)))
  })

  return `gs://${bucketName}/${gcsPath}`
}
