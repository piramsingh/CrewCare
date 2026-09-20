/**
 * The WhatsApp server reads `server/whatsapp/script.json`, generated from
 * `src/conversation/script.ts`. If someone edits the script and forgets to
 * re-export, the phone and the browser start saying different things — and
 * nothing else would catch it. This test does.
 */
import { readFileSync } from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

import { buildExport } from '../scripts/export-conversation.mts'

const COMMITTED = new URL('../server/whatsapp/script.json', import.meta.url)

test('the exported script matches src/conversation/script.ts', () => {
  const onDisk = JSON.parse(readFileSync(COMMITTED, 'utf8'))
  assert.deepEqual(
    onDisk,
    buildExport(),
    'server/whatsapp/script.json is stale — run: npm run export:conversation',
  )
})

test('every step the server can land on is reachable and terminates', () => {
  const { steps, firstStep } = buildExport()
  const byId = new Map(steps.map((s) => [s.id, s]))

  const seen = new Set<string>()
  const queue = [firstStep]
  while (queue.length) {
    const id = queue.pop()!
    if (seen.has(id)) continue
    seen.add(id)
    const step = byId.get(id)
    assert.ok(step, `step "${id}" is referenced but does not exist`)
    for (const target of [step.next, step.skipTo, ...Object.values(step.branch ?? {})]) {
      if (target) queue.push(target)
    }
  }

  assert.ok(seen.has('done'), 'the conversation can reach its end')
  for (const step of steps) {
    assert.ok(seen.has(step.id), `step "${step.id}" is unreachable from ${firstStep}`)
  }
})
