import { encrypt, decrypt } from '../src/services/encryption'

const VALID_KEY = 'a'.repeat(64) // 32 bytes as 64 hex chars

describe('encryption', () => {
  beforeEach(() => {
    process.env.TOKEN_ENCRYPTION_KEY = VALID_KEY
  })

  afterEach(() => {
    delete process.env.TOKEN_ENCRYPTION_KEY
  })

  describe('encrypt', () => {
    it('returns a Buffer', () => {
      const result = encrypt('hello')
      expect(Buffer.isBuffer(result)).toBe(true)
    })

    it('produces different ciphertext for the same plaintext (random IV)', () => {
      const a = encrypt('same-text')
      const b = encrypt('same-text')
      // iv is random, so outputs must differ
      expect(a.equals(b)).toBe(false)
    })

    it('output is at least 29 bytes (12 iv + 16 tag + 1 char)', () => {
      const result = encrypt('x')
      expect(result.length).toBeGreaterThanOrEqual(29)
    })

    it('throws when TOKEN_ENCRYPTION_KEY is missing', () => {
      delete process.env.TOKEN_ENCRYPTION_KEY
      expect(() => encrypt('hello')).toThrow('TOKEN_ENCRYPTION_KEY not configured')
    })

    it('throws when key is wrong length', () => {
      process.env.TOKEN_ENCRYPTION_KEY = 'tooshort'
      expect(() => encrypt('hello')).toThrow('TOKEN_ENCRYPTION_KEY must be 32 bytes')
    })
  })

  describe('decrypt', () => {
    it('round-trips a short string', () => {
      const plaintext = 'access-token-value'
      const ciphertext = encrypt(plaintext)
      expect(decrypt(ciphertext)).toBe(plaintext)
    })

    it('round-trips a long string (OAuth token-like)', () => {
      const plaintext = 'ya29.' + 'A'.repeat(200)
      const ciphertext = encrypt(plaintext)
      expect(decrypt(ciphertext)).toBe(plaintext)
    })

    it('round-trips a string with special characters', () => {
      const plaintext = 'token with spaces & "quotes" and <tags>'
      expect(decrypt(encrypt(plaintext))).toBe(plaintext)
    })

    it('throws on tampered ciphertext (auth tag mismatch)', () => {
      const ciphertext = encrypt('original')
      // Flip a byte in the ciphertext portion (after iv + tag = 28 bytes)
      const tampered = Buffer.from(ciphertext)
      tampered[28] ^= 0xff
      expect(() => decrypt(tampered)).toThrow()
    })

    it('throws when TOKEN_ENCRYPTION_KEY is missing', () => {
      const ciphertext = encrypt('hello')
      delete process.env.TOKEN_ENCRYPTION_KEY
      expect(() => decrypt(ciphertext)).toThrow('TOKEN_ENCRYPTION_KEY not configured')
    })

    it('multiple encryptions of the same text all round-trip correctly', () => {
      const plaintext = 'multi-test'
      for (let i = 0; i < 5; i++) {
        expect(decrypt(encrypt(plaintext))).toBe(plaintext)
      }
    })
  })
})
