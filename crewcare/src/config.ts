/**
 * Where the WhatsApp server lives, and which number workers text.
 *
 * Both are overridable at build time so a deployed demo does not need a code
 * change:  VITE_API_BASE=https://…  VITE_WHATSAPP_NUMBER=15551558045
 *
 * The defaults are the local dev server and the Meta test number.
 */
export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

/** Digits only, country code first — the format wa.me links require. */
export const WHATSAPP_NUMBER = import.meta.env.VITE_WHATSAPP_NUMBER ?? '15551558045'

/** Pretty form for display. */
export const WHATSAPP_NUMBER_DISPLAY = '+1 (555) 155-8045'

/** Opens WhatsApp with the linking code already typed. */
export function whatsappDeepLink(code: string): string {
  return `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(code)}`
}
