import { Router, Request, Response } from 'express'
import { google } from 'googleapis'
import jwt from 'jsonwebtoken'
import { z } from 'zod'
import { pool } from '../db/client'
import { encrypt } from '../services/encryption'
import { requireAuth } from '../middleware/auth'

const router = Router()

// ─── Validation schemas ─────────────────────────────────────────────────────

const GoogleCallbackSchema = z.object({
  code: z.string().min(1),
})

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getOAuthClient() {
  const clientId = process.env.GOOGLE_CLIENT_ID
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET
  const redirectUri = process.env.GOOGLE_REDIRECT_URI

  if (!clientId) throw new Error('GOOGLE_CLIENT_ID not configured')
  if (!clientSecret) throw new Error('GOOGLE_CLIENT_SECRET not configured')
  if (!redirectUri) throw new Error('GOOGLE_REDIRECT_URI not configured')

  return new google.auth.OAuth2(clientId, clientSecret, redirectUri)
}

function getJwtSecret(): string {
  const secret = process.env.JWT_SECRET
  if (!secret) throw new Error('JWT_SECRET not configured')
  return secret
}

function buildSessionCookie(userId: string, email: string, googleId: string): string {
  return jwt.sign(
    { id: userId, email, googleId },
    getJwtSecret(),
    { expiresIn: '7d' },
  )
}

// ─── POST /api/auth/google/callback ──────────────────────────────────────────

/**
 * Exchange Google OAuth2 authorization code for tokens.
 * Encrypts tokens and upserts user record in DB.
 * Sets httpOnly + Secure + SameSite=Strict session cookie.
 * Never returns tokens in the response body.
 */
router.post('/google/callback', async (req: Request, res: Response) => {
  const parsed = GoogleCallbackSchema.safeParse(req.body)
  if (!parsed.success) {
    res.status(400).json({ error: 'Invalid request', details: parsed.error.flatten() })
    return
  }

  try {
    const oauth2Client = getOAuthClient()
    const { tokens } = await oauth2Client.getToken(parsed.data.code)

    if (!tokens.access_token || !tokens.refresh_token || !tokens.expiry_date) {
      res.status(400).json({ error: 'Incomplete token response from Google' })
      return
    }

    // Fetch user profile
    oauth2Client.setCredentials(tokens)
    const oauth2 = google.oauth2({ version: 'v2', auth: oauth2Client })
    const { data: profile } = await oauth2.userinfo.get()

    if (!profile.id || !profile.email) {
      res.status(400).json({ error: 'Could not retrieve Google profile' })
      return
    }

    const encryptedAccess = encrypt(tokens.access_token)
    const encryptedRefresh = encrypt(tokens.refresh_token)
    const tokenExpiresAt = new Date(tokens.expiry_date).toISOString()
    // Use a static key version identifier — in production this would be KMS key version
    const encryptionKeyId = 'v1'

    // Upsert user — conflict on google_id updates tokens + timestamp
    const result = await pool.query<{ id: string; email: string; google_id: string }>(
      `INSERT INTO users
         (email, display_name, google_id, access_token_enc, refresh_token_enc,
          token_expires_at, encryption_key_id)
       VALUES ($1, $2, $3, $4, $5, $6, $7)
       ON CONFLICT (google_id) DO UPDATE SET
         email              = EXCLUDED.email,
         display_name       = EXCLUDED.display_name,
         access_token_enc   = EXCLUDED.access_token_enc,
         refresh_token_enc  = EXCLUDED.refresh_token_enc,
         token_expires_at   = EXCLUDED.token_expires_at,
         encryption_key_id  = EXCLUDED.encryption_key_id,
         updated_at         = NOW()
       RETURNING id, email, google_id`,
      [
        profile.email,
        profile.name ?? null,
        profile.id,
        encryptedAccess,
        encryptedRefresh,
        tokenExpiresAt,
        encryptionKeyId,
      ],
    )

    const user = result.rows[0]
    const sessionToken = buildSessionCookie(user.id, user.email, user.google_id)

    const isProduction = process.env.NODE_ENV === 'production'

    res
      .cookie('session', sessionToken, {
        httpOnly: true,
        secure: isProduction,
        sameSite: 'strict',
        maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days in ms
      })
      .status(200)
      .json({ ok: true })
  } catch (error) {
    // Do not leak error details to the client
    console.error('[auth/google/callback] error:', error)
    res.status(500).json({ error: 'Authentication failed' })
  }
})

// ─── GET /api/auth/me ─────────────────────────────────────────────────────────

/**
 * Returns the authenticated user's public profile.
 * Relies on the requireAuth middleware to validate the session cookie.
 */
router.get('/me', requireAuth, async (req: Request, res: Response) => {
  try {
    const result = await pool.query<{
      id: string
      email: string
      display_name: string | null
      google_id: string
      created_at: string
    }>(
      `SELECT id, email, display_name, google_id, created_at
       FROM users
       WHERE id = $1`,
      [req.user!.id],
    )

    if (result.rows.length === 0) {
      res.status(404).json({ error: 'User not found' })
      return
    }

    const { id, email, display_name, google_id, created_at } = result.rows[0]

    res.json({
      id,
      email,
      displayName: display_name,
      googleId: google_id,
      createdAt: created_at,
    })
  } catch (error) {
    console.error('[auth/me] error:', error)
    res.status(500).json({ error: 'Failed to retrieve user profile' })
  }
})

export default router
