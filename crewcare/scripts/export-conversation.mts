/**
 * Export the conversation script to JSON for the WhatsApp server.
 *
 * `src/conversation/script.ts` is the single source of truth for what
 * CrewCare says. The Python service cannot import TypeScript, so it reads
 * this generated file instead — which keeps one copy of the wording rather
 * than two that drift.
 *
 * Run: npm run export:conversation
 * A test (test/script-export.test.ts) fails if the committed JSON is stale.
 */
import { writeFileSync } from 'node:fs'

import { DISCLOSURE, FIRST_STEP, script, type Line, type Step } from '../src/conversation/script.ts'

/** The server delivers over WhatsApp, so channel overrides resolve to that. */
const CHANNEL = 'whatsapp' as const

type ExportedLine = { text: string; sample?: true } | { special: 'summary' }

function exportLine(line: Line): ExportedLine {
  if (typeof line === 'string') return { text: line }
  if ('special' in line) return { special: line.special }
  return line.sample ? { text: line.text, sample: true } : { text: line.text }
}

function exportStep(step: Step) {
  const override = step.byChannel?.[CHANNEL]
  const lines = (override?.lines ?? step.lines).map(exportLine)
  const options =
    override?.options ?? ('options' in step ? step.options : undefined)

  return {
    id: step.id,
    kind: step.kind,
    lines,
    ...(options ? { options } : {}),
    ...(step.ack ? { ack: step.ack } : {}),
    ...(step.skipAck ? { skipAck: step.skipAck } : {}),
    ...(step.next ? { next: step.next } : {}),
    ...(step.branch ? { branch: step.branch } : {}),
    ...(step.allowSkip ? { allowSkip: true } : {}),
    ...(step.skipTo ? { skipTo: step.skipTo } : {}),
    ...(step.skipLabel ? { skipLabel: step.skipLabel } : {}),
    ...(step.summaryLabel ? { summaryLabel: step.summaryLabel } : {}),
    ...('placeholder' in step ? { placeholder: step.placeholder } : {}),
    ...('actionLabel' in step ? { actionLabel: step.actionLabel } : {}),
    ...('scopes' in step ? { scopes: step.scopes } : {}),
    ...('accept' in step ? { accept: step.accept } : {}),
  }
}

export function buildExport() {
  return {
    _generated: 'npm run export:conversation — edit src/conversation/script.ts, not this file',
    channel: CHANNEL,
    firstStep: FIRST_STEP,
    disclosure: DISCLOSURE,
    steps: script.map(exportStep),
  }
}

const OUT = new URL('../server/whatsapp/script.json', import.meta.url)

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].split('/').pop()!)) {
  writeFileSync(OUT, JSON.stringify(buildExport(), null, 2) + '\n')
  console.log(`wrote ${OUT.pathname}`)
}
