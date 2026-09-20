/**
 * The only module in the app that talks to a server.
 *
 * Everything else runs offline: the simulated thread, the admin dashboard and
 * the sign-in screen all work with no network at all. A request is made here
 * only when a worker explicitly asks to link their phone, which is the one
 * point where this stops being a self-contained demo.
 *
 * The employee id is sent in a header because the server's demo auth reads it
 * there. In a real build that header is replaced by the session the worker
 * already holds, and the server never trusts a client-supplied id.
 */
import { API_BASE } from '../config'

export type LinkingCode = {
  code: string
  expiresAt: Date
}

export class LinkingError extends Error {}

export async function requestLinkingCode(employeeId: string): Promise<LinkingCode> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}/api/whatsapp/linking/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Demo-Employee-Id': employeeId },
    })
  } catch {
    throw new LinkingError(`Can't reach the CrewCare server at ${API_BASE}. Is it running?`)
  }

  if (!response.ok) {
    throw new LinkingError(`The server refused the request (${response.status}).`)
  }

  const body = (await response.json()) as { code: string; expires_at: string }
  return { code: body.code, expiresAt: new Date(body.expires_at) }
}
