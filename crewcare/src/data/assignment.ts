/**
 * The worker's assignment, as the agency holds it.
 *
 * Read-only by design and deliberately not part of the conversation: the
 * roster lives in the MTA's back end and is not the worker's to change from a
 * messaging thread. It is shown as standing context at the top of the screen
 * rather than asked about, so it never costs the worker a tap.
 *
 * In production this is a read from the agency's system, refreshed per day.
 * Here it is hard-coded, because there is no back end.
 */
export type Assignment = {
  role: string
  station: string
}

export const ASSIGNMENT_ON_FILE: Assignment = {
  role: 'Track Worker',
  station: 'Times Square–42nd Street',
}
