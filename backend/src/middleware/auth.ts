import { Request, Response, NextFunction } from 'express'
import jwt from 'jsonwebtoken'

export interface AuthUser {
  id: string
  email: string
  googleId: string
}

// Extend Express Request so downstream handlers get typed req.user
declare global {
  namespace Express {
    interface Request {
      user?: AuthUser
    }
  }
}

function getJwtSecret(): string {
  const secret = process.env.JWT_SECRET
  if (!secret) throw new Error('JWT_SECRET not configured')
  return secret
}

/**
 * Middleware: extract and verify the JWT from the httpOnly session cookie.
 * Attaches req.user on success; returns 401 on missing or invalid token.
 *
 * Never leaks token contents or stack traces to the client.
 */
export function requireAuth(
  req: Request,
  res: Response,
  next: NextFunction,
): void {
  const token: string | undefined = req.cookies?.session

  if (!token) {
    res.status(401).json({ error: 'Authentication required' })
    return
  }

  try {
    const secret = getJwtSecret()
    const payload = jwt.verify(token, secret) as AuthUser & jwt.JwtPayload

    req.user = {
      id: payload.id,
      email: payload.email,
      googleId: payload.googleId,
    }

    next()
  } catch {
    res.status(401).json({ error: 'Invalid or expired session' })
  }
}
