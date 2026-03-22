import { createCipheriv, createDecipheriv, randomBytes } from 'crypto'

const ALGORITHM = 'aes-256-gcm'
const IV_LENGTH = 12   // 96-bit IV recommended for GCM
const TAG_LENGTH = 16  // 128-bit auth tag

function getKey(): Buffer {
  const key = process.env.TOKEN_ENCRYPTION_KEY
  if (!key) throw new Error('TOKEN_ENCRYPTION_KEY not configured')

  const buf = Buffer.from(key, 'hex')
  if (buf.length !== 32) {
    throw new Error('TOKEN_ENCRYPTION_KEY must be 32 bytes (64 hex chars)')
  }
  return buf
}

/**
 * Encrypts a UTF-8 plaintext string using AES-256-GCM.
 *
 * Wire format (all concatenated into one Buffer):
 *   iv (12 bytes) | authTag (16 bytes) | ciphertext (variable)
 *
 * Storing authTag before ciphertext allows decryption to extract it
 * without knowing the ciphertext length up front.
 */
export function encrypt(plaintext: string): Buffer {
  const key = getKey()
  const iv = randomBytes(IV_LENGTH)
  const cipher = createCipheriv(ALGORITHM, key, iv)

  const encrypted = Buffer.concat([
    cipher.update(plaintext, 'utf8'),
    cipher.final(),
  ])
  const tag = cipher.getAuthTag()

  // iv(12) + tag(16) + ciphertext
  return Buffer.concat([iv, tag, encrypted])
}

/**
 * Decrypts a Buffer produced by `encrypt`.
 * Throws on tampered data (GCM auth tag mismatch).
 */
export function decrypt(data: Buffer): string {
  const key = getKey()

  const iv = data.subarray(0, IV_LENGTH)
  const tag = data.subarray(IV_LENGTH, IV_LENGTH + TAG_LENGTH)
  const encrypted = data.subarray(IV_LENGTH + TAG_LENGTH)

  const decipher = createDecipheriv(ALGORITHM, key, iv)
  decipher.setAuthTag(tag)

  return decipher.update(encrypted).toString('utf8') + decipher.final('utf8')
}
