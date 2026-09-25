/**
 * Where the operations API lives.
 *
 * In development the API runs separately on :8000. In a deployment the two
 * are served from one origin — Vercel routes /api/ops/* to the Python
 * function — so the base is empty and requests stay same-origin. Getting this
 * wrong is silent: a built app would call the visitor's own localhost.
 *
 * VITE_API_BASE overrides both, for an API hosted somewhere else.
 */
export const API_BASE =
  import.meta.env.VITE_API_BASE ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')
