/**
 * Simulated role resolution — the single swap point for real authentication.
 *
 * DEMO ONLY. There is no directory lookup, no credential check, no network
 * call. When this prototype is wired to real auth, replace the body of
 * `resolveRole` with the identity provider's claim and delete `DEMO_HINT`.
 * Nothing else in the app needs to change.
 *
 * The resolution rule is deliberately never surfaced in the UI. The app routes
 * on the resolved role; it never asks the person which one they are.
 */
export type Role = 'worker' | 'admin'

/**
 * W-prefixed employee IDs resolve to workers, A-prefixed to administrators.
 * Everything else — including an empty field — resolves to worker, which is
 * the default demo path.
 *
 * The argument is used to compute the role and is not retained by this module.
 */
export function resolveRole(employeeId: string): Role {
  const prefix = employeeId.trim().charAt(0).toUpperCase()
  if (prefix === 'A') return 'admin'
  return 'worker'
}

/**
 * Stand-in id for someone who signs in with the field empty.
 *
 * An empty field is a valid demo path — the brief requires it — but linking a
 * phone needs *some* id to tie the WhatsApp number to, and sending an empty
 * one just produces a 401 the person cannot act on. This keeps the empty path
 * working end to end.
 */
export const DEMO_EMPLOYEE_ID = 'W0000'

/** The id to carry for this session: what was typed, or the demo stand-in. */
export function sessionEmployeeId(typed: string): string {
  return typed.trim() || DEMO_EMPLOYEE_ID
}

/** Operator-facing hint shown under the Continue button. Not the rule itself. */
export const DEMO_HINT = 'Demo: any ID works. Try W1042 or A0117.'
