/**
 * Where the operations API lives.
 *
 * Overridable at build time so a deployed dashboard needs no code change:
 *   VITE_API_BASE=https://…
 *
 * Only the admin dashboard uses this. The worker demo makes no requests.
 */
export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'
