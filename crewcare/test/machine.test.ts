/**
 * The conversation machine, exercised with no UI at all.
 * Run with `npm test` (Node strips the types natively).
 */
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  answerText,
  approveConnection,
  attachFile,
  beginReport,
  canGoBack,
  cancelReport,
  canSkip,
  chooseOption,
  createState,
  dismissConnection,
  goBack,
  currentStep,
  inputMode,
  optionsFor,
  phaseOf,
  skip,
  submitReport,
  summaryRows,
  tick,
  type State,
} from '../src/conversation/machine.ts'
import type { Channel } from '../src/theme.ts'
import { DISCLOSURE } from '../src/conversation/script.ts'

/** Drain every queued bot line, as the UI does after each typing beat. */
function settle(state: State): State {
  let next = state
  while (phaseOf(next) === 'thinking') next = tick(next)
  return next
}

const texts = (state: State) =>
  state.messages.flatMap((m) => (m.kind === 'text' ? [m.text] : []))

test('intro states the disclosure verbatim before any health question', () => {
  const state = settle(createState())
  assert.ok(texts(state).includes(DISCLOSURE))
  assert.equal(currentStep(state)?.id, 'intro')
  assert.equal(inputMode(state), 'choice')
})

test('"What is this?" detours through the explainer and returns to Q1', () => {
  let state = settle(createState())
  state = settle(chooseOption(state, 'about'))
  assert.equal(currentStep(state)?.id, 'about')
  state = settle(chooseOption(state, 'start'))
  assert.equal(currentStep(state)?.id, 'q1')
})

test('Q2 branch — "Yes" continues into the symptom questions', () => {
  let state = settle(createState())
  state = settle(chooseOption(state, 'start'))
  state = settle(chooseOption(state, 'good'))
  assert.equal(currentStep(state)?.id, 'q2')
  state = settle(chooseOption(state, 'yes'))
  assert.equal(currentStep(state)?.id, 'q3')
  assert.equal(inputMode(state), 'text')
  state = settle(answerText(state, 'Dry cough after midnights'))
  assert.equal(currentStep(state)?.id, 'q4')
  state = settle(chooseOption(state, '1-4-weeks'))
  assert.equal(currentStep(state)?.id, 'q5')
  state = settle(chooseOption(state, 'during-work'))
  assert.equal(currentStep(state)?.id, 'medical')
})

test('Q2 branch — "No" skips the symptom questions entirely', () => {
  let state = settle(createState())
  state = settle(chooseOption(state, 'start'))
  state = settle(chooseOption(state, 'fair'))
  state = settle(chooseOption(state, 'no'))
  assert.equal(currentStep(state)?.id, 'medical')
  assert.equal(state.answers.q3, undefined)
})

test('Q2 branch — "Prefer not to say" also skips to the schedule', () => {
  let state = settle(createState())
  state = settle(chooseOption(state, 'start'))
  state = settle(chooseOption(state, 'prefer-not'))
  state = settle(chooseOption(state, 'prefer-not'))
  assert.equal(currentStep(state)?.id, 'medical')
})

test('every health question accepts a skip without follow-up', () => {
  let state = settle(createState())
  state = settle(chooseOption(state, 'start'))
  assert.equal(currentStep(state)?.id, 'q1')
  state = settle(skip(state))
  assert.equal(currentStep(state)?.id, 'q2')
  state = settle(skip(state))
  // Declining Q2 is treated as declining to elaborate.
  assert.equal(currentStep(state)?.id, 'medical')
  assert.ok(state.answers.q1.skipped)
})

test('the bot only ever acknowledges, never interprets, a health answer', () => {
  let state = settle(createState())
  state = settle(chooseOption(state, 'start'))
  const before = state.messages.length
  state = settle(chooseOption(state, 'poor'))
  const added = state.messages.slice(before)
  const botLines = added.flatMap((m) => (m.from === 'bot' && m.kind === 'text' ? [m.text] : []))
  assert.equal(botLines[0], 'Got it.')
  // Nothing said about the answer itself beyond the next question.
  assert.equal(botLines.length, 2)
  assert.match(botLines[1], /^Are you currently experiencing/)
})

test('the assignment costs the worker no turn and no tap', () => {
  const state = toMedical()
  // It is chrome, not conversation: nothing about it reaches the transcript.
  const said = texts(state).join(' ')
  assert.ok(!/Track Worker|Times Square|division has you down/i.test(said))
  assert.ok(!state.messages.some((m) => m.kind !== 'text'), 'no card is emitted')
  assert.equal(state.answers.assignment, undefined, 'nothing is recorded for it')
  // Q2 "No" lands straight on the medical step, with nothing in between.
  assert.equal(currentStep(state)?.id, 'medical')
})

test('a full run reaches Stage E with a summary of what was captured', () => {
  let state = settle(createState())
  state = settle(chooseOption(state, 'start'))
  state = settle(chooseOption(state, 'very-good'))
  state = settle(chooseOption(state, 'yes'))
  state = settle(answerText(state, 'Shortness of breath'))
  state = settle(chooseOption(state, '1-3-months'))
  state = settle(chooseOption(state, 'after-work'))
  state = settle(attachFile(state, { name: 'note.pdf', url: 'blob:demo', isImage: false }))
  state = chooseOption(state, 'apple')
  state = settle(approveConnection(state, ['Respiratory rate', 'Sleep']))
  assert.equal(currentStep(state)?.id, 'notify')
  state = settle(chooseOption(state, 'daily'))
  state = beginReport(state)
  state = settle(submitReport(state, 'Dust everywhere on the northbound side', 'Times Square–42nd Street'))

  assert.equal(phaseOf(state), 'done')
  const sample = state.messages.find((m) => m.kind === 'text' && m.sample)
  assert.ok(sample, 'sample alert is emitted and marked as a sample')
  const rows = summaryRows(state)
  assert.deepEqual(
    rows.map((r) => r.label),
    ['Overall health', 'Current concern', 'Main problem', 'Duration', 'Pattern', 'Medical records', 'Health app', 'Shift alerts', 'Station report'],
  )
  assert.equal(rows[2].value, 'Shortness of breath')
  assert.equal(rows[5].value, 'note.pdf · stays on your phone')
  // Role and station are chrome, not something the worker shared.
  assert.ok(!rows.some((r) => r.label === 'Role' || r.label === 'Station'))
})

test('medical records are optional and can be declined', () => {
  let state = toMedical()
  assert.equal(currentStep(state)?.id, 'medical')
  assert.equal(inputMode(state), 'attach')
  assert.ok(canSkip(state), 'the step always offers a way past it')

  const said = texts(state).join(' ')
  assert.match(said, /Nobody else sees it/)
  // The worker is never told about the dashboard: it is not their concern and
  // naming it would introduce a thing they otherwise have no reason to know.
  assert.ok(!/dashboard|report|aggregate/i.test(said))

  state = settle(skip(state))
  assert.equal(currentStep(state)?.id, 'health_app')
  assert.deepEqual(state.attachments, [], 'nothing is held when the step is skipped')
})

test('an attached document is acknowledged, never interpreted', () => {
  let state = toMedical()
  const before = state.messages.length
  state = settle(
    attachFile(state, { name: 'restriction.pdf', url: 'blob:demo', isImage: false }),
  )
  assert.deepEqual(state.attachments, [
    { name: 'restriction.pdf', url: 'blob:demo', isImage: false },
  ])
  assert.equal(currentStep(state)?.id, 'health_app')

  // The bot acknowledges receipt and says nothing about the contents.
  const botLines = state.messages
    .slice(before)
    .flatMap((m) => (m.from === 'bot' && m.kind === 'text' ? [m.text] : []))
  assert.equal(botLines[0], 'Got it. That stays on your phone.')
})

/** Settled state sitting on the optional medical-records step. */
function toMedical(channel: Channel = 'whatsapp'): State {
  let state = settle(createState(channel))
  state = settle(chooseOption(state, 'start'))
  state = settle(chooseOption(state, 'good'))
  state = settle(chooseOption(state, 'no'))
  return state
}

/** Settled state sitting on the health-app step, medical records declined. */
function toHealthApp(channel: Channel = 'whatsapp'): State {
  return settle(skip(toMedical(channel)))
}

test('WhatsApp offers both providers, because the platform is unknown', () => {
  const state = toHealthApp('whatsapp')
  assert.equal(currentStep(state)?.id, 'health_app')
  assert.equal(inputMode(state), 'connect')
  assert.ok(canSkip(state))
  const step = currentStep(state)!
  assert.deepEqual(
    optionsFor(step, 'whatsapp').map((o) => o.id),
    ['apple', 'commonhealth'],
  )
  const said = texts(state).join(' ')
  assert.match(said, /Apple Health or CommonHealth/)
  assert.match(said, /stays on your phone/)
  assert.ok(!/dashboard|report|aggregate/i.test(said))
})

test('iMessage offers only Apple Health, because it implies an iPhone', () => {
  const state = toHealthApp('imessage')
  const step = currentStep(state)!
  assert.deepEqual(optionsFor(step, 'imessage').map((o) => o.id), ['apple'])
  const said = texts(state).join(' ')
  assert.match(said, /connect your Apple Health account/)
  assert.ok(!/CommonHealth/.test(said), 'an Android-only provider is never offered on iOS')
})

test('the two channels differ only at the health-app step', () => {
  const ios = texts(toHealthApp('imessage'))
  const android = texts(toHealthApp('whatsapp'))
  // Everything before the last three lines (the connect prompt) is identical.
  assert.deepEqual(ios.slice(0, -3), android.slice(0, -3))
})

test('picking a provider grants nothing until the sheet is allowed', () => {
  let state = toHealthApp()
  state = chooseOption(state, 'apple')
  assert.equal(phaseOf(state), 'connecting')
  assert.equal(state.connecting, 'apple')
  assert.equal(state.connection, null, 'nothing is granted by opening the sheet')
  assert.equal(currentStep(state)?.id, 'health_app', 'the step has not advanced')

  // Backing out leaves the worker exactly where they were.
  state = dismissConnection(state)
  assert.equal(state.connection, null)
  assert.equal(phaseOf(state), 'awaiting')
  assert.equal(currentStep(state)?.id, 'health_app')
})

test('only the data types the worker ticked are granted', () => {
  let state = toHealthApp()
  state = chooseOption(state, 'apple')
  state = settle(approveConnection(state, ['Respiratory rate', 'Blood oxygen']))

  assert.deepEqual(state.connection, {
    provider: 'Apple Health',
    scopes: ['Respiratory rate', 'Blood oxygen'],
  })
  assert.equal(currentStep(state)?.id, 'notify')
  assert.equal(
    summaryRows(state).find((r) => r.label === 'Health app')?.value,
    'Apple Health · 2 of 4 types',
  )
})

test('an empty grant is not a connection', () => {
  let state = toHealthApp()
  state = chooseOption(state, 'commonhealth')
  const after = approveConnection(state, [])
  assert.equal(after.connection, null)
  assert.equal(after.connecting, 'commonhealth', 'the sheet stays open')
})

test('skipping the health-app step connects nothing', () => {
  let state = toHealthApp()
  state = settle(skip(state))
  assert.equal(state.connection, null)
  assert.equal(currentStep(state)?.id, 'notify')
})

test('declining alerts does not enrol the worker', () => {
  let state = toHealthApp()
  state = settle(skip(state))
  assert.equal(currentStep(state)?.id, 'notify')
  state = settle(chooseOption(state, 'none'))

  const said = texts(state).join(' ')
  assert.ok(!state.messages.some((m) => m.kind === 'text' && m.sample), 'no sample alert is sent')
  assert.ok(!/all set/i.test(said), 'the worker is not told they are set up')
  assert.ok(!/Reply STOP/i.test(said), 'no unsubscribe instructions for a subscription that does not exist')
  assert.match(said, /won’t message you/)
  assert.match(said, /reply START/i, 'a way back in is offered')
  assert.equal(currentStep(state)?.id, 'complaint')
  assert.equal(summaryRows(state).find((r) => r.label === 'Shift alerts')?.value, 'No thanks')
})

test('opting in still confirms and shows a sample', () => {
  let state = toHealthApp()
  state = settle(skip(state))
  state = settle(chooseOption(state, 'big-changes'))
  assert.ok(state.messages.some((m) => m.kind === 'text' && m.sample), 'sample alert is sent')
  assert.match(texts(state).join(' '), /Reply STOP/)
})

test('a mistapped answer can be taken back', () => {
  let state = settle(createState())
  assert.ok(!canGoBack(state), 'nothing to undo before the first answer')
  state = settle(chooseOption(state, 'start'))

  // Meant to tap Poor, tapped Excellent.
  state = settle(chooseOption(state, 'excellent'))
  assert.equal(currentStep(state)?.id, 'q2')
  assert.ok(canGoBack(state))

  state = goBack(state)
  assert.equal(currentStep(state)?.id, 'q1', 'the question is live again')
  assert.equal(state.answers.q1, undefined, 'the wrong answer is gone')
  assert.ok(!texts(state).includes('Excellent'), 'and so is the reply in the thread')
  assert.equal(phaseOf(state), 'awaiting')

  state = settle(chooseOption(state, 'poor'))
  assert.equal(state.answers.q1.label, 'Poor')
  assert.equal(currentStep(state)?.id, 'q2')
})

test('going back repeatedly walks the whole way out', () => {
  let state = settle(createState())
  state = settle(chooseOption(state, 'start'))
  state = settle(chooseOption(state, 'good'))
  state = settle(chooseOption(state, 'yes'))
  state = settle(answerText(state, 'Dry cough'))
  assert.equal(currentStep(state)?.id, 'q4')

  state = goBack(state)
  assert.equal(currentStep(state)?.id, 'q3')
  state = goBack(state)
  assert.equal(currentStep(state)?.id, 'q2')
  state = goBack(state)
  assert.equal(currentStep(state)?.id, 'q1')
  state = goBack(state)
  assert.equal(currentStep(state)?.id, 'intro')
  assert.ok(!canGoBack(state), 'and stops at the start')
  assert.deepEqual(state.answers, {})
})

test('going back off a branch discards the answers that branch produced', () => {
  let state = settle(createState())
  state = settle(chooseOption(state, 'start'))
  state = settle(chooseOption(state, 'good'))
  state = settle(chooseOption(state, 'yes'))
  state = settle(answerText(state, 'Dry cough'))
  state = settle(chooseOption(state, '1-3-days'))
  assert.equal(currentStep(state)?.id, 'q5')

  // Back out of the symptom branch entirely and answer "No" instead.
  state = goBack(state)
  state = goBack(state)
  state = goBack(state)
  assert.equal(currentStep(state)?.id, 'q2')
  state = settle(chooseOption(state, 'no'))

  assert.equal(currentStep(state)?.id, 'medical')
  assert.equal(state.answers.q3, undefined, 'the symptom text does not survive')
  assert.equal(state.answers.q4, undefined)
  assert.ok(!texts(state).includes('Dry cough'))
  assert.ok(!summaryRows(state).some((r) => r.label === 'Main problem'))
})

test('going back un-attaches a document and un-grants a connection', () => {
  let state = toMedical()
  state = settle(attachFile(state, { name: 'note.pdf', url: 'blob:demo', isImage: false }))
  assert.deepEqual(state.attachments.map((a) => a.name), ['note.pdf'], 'precondition')
  state = chooseOption(state, 'apple')
  state = settle(approveConnection(state, ['Sleep']))
  assert.equal(currentStep(state)?.id, 'notify')

  state = goBack(state)
  assert.equal(state.connection, null, 'the grant is withdrawn')
  assert.equal(state.connecting, null, 'and the sheet does not reopen')
  assert.equal(currentStep(state)?.id, 'health_app')

  state = goBack(state)
  assert.deepEqual(state.attachments, [], 'the document is no longer held')
  assert.equal(currentStep(state)?.id, 'medical')
})

test('the last answer can be changed from the summary', () => {
  let state = toHealthApp()
  state = settle(skip(state))
  state = settle(chooseOption(state, 'daily'))
  state = settle(skip(state))
  assert.equal(phaseOf(state), 'done')
  assert.ok(canGoBack(state), 'Back is still offered at the end')

  state = goBack(state)
  assert.equal(currentStep(state)?.id, 'complaint')
  state = goBack(state)
  assert.equal(currentStep(state)?.id, 'notify')
  state = settle(chooseOption(state, 'none'))
  state = settle(skip(state))
  assert.equal(
    summaryRows(state).find((r) => r.label === 'Shift alerts')?.value,
    'No thanks',
  )
  assert.ok(!/Reply STOP/i.test(texts(state).join(' ')), 'and the enrolled path is gone')
})

/** Settled state sitting on the complaint step, having enrolled in alerts. */
function toComplaint(): State {
  let state = settle(skip(toHealthApp()))
  state = settle(chooseOption(state, 'daily'))
  return state
}

test('the complaint CTA follows the alerts step on both paths', () => {
  const enrolled = toComplaint()
  assert.equal(currentStep(enrolled)?.id, 'complaint')
  assert.equal(inputMode(enrolled), 'report')

  // Declining alerts must not cost the worker the ability to complain.
  let declined = settle(skip(toHealthApp()))
  declined = settle(chooseOption(declined, 'none'))
  assert.equal(currentStep(declined)?.id, 'complaint')
})

test('opening the form files nothing', () => {
  let state = beginReport(toComplaint())
  assert.equal(phaseOf(state), 'reporting')
  assert.equal(state.report, null)

  state = cancelReport(state)
  assert.equal(state.report, null)
  assert.equal(currentStep(state)?.id, 'complaint', 'the step stands')
  assert.equal(phaseOf(state), 'awaiting')
})

test('a complaint carries where and what, and nothing about the person', () => {
  let state = beginReport(toComplaint())
  state = settle(
    submitReport(state, 'Grinding crew all shift, no ventilation', 'Times Square–42nd Street'),
  )

  assert.deepEqual(state.report, {
    station: 'Times Square–42nd Street',
    detail: 'Grinding crew all shift, no ventilation',
  })
  // The one outbound object holds exactly two fields.
  assert.deepEqual(Object.keys(state.report!).sort(), ['detail', 'station'])
  assert.equal(phaseOf(state), 'done')
  assert.match(texts(state).join(' '), /Nothing about your health goes with it/)
})

test('a complaint cannot be filed empty', () => {
  const state = beginReport(toComplaint())
  for (const empty of ['', '   ', '\n']) {
    const after = submitReport(state, empty, 'Times Square–42nd Street')
    assert.equal(after.report, null, `"${empty}" should not file`)
    assert.equal(after.reporting, true, 'the box stays open')
  }
})

test('the complaint step can be declined', () => {
  let state = settle(skip(toComplaint()))
  assert.equal(state.report, null)
  assert.equal(phaseOf(state), 'done')
  assert.equal(
    summaryRows(state).find((r) => r.label === 'Station report')?.value,
    'Skipped',
  )
})

test('going back un-files a complaint', () => {
  let state = beginReport(toComplaint())
  state = settle(submitReport(state, 'Vent has been out for a week', 'Times Square–42nd Street'))
  assert.ok(state.report)

  state = goBack(state)
  assert.equal(state.report, null, 'the complaint is withdrawn')
  assert.equal(state.reporting, false, 'and the form does not reopen')
  assert.equal(currentStep(state)?.id, 'complaint')
})

test('skipping a step never claims the action happened', () => {
  // Every step whose acknowledgement describes an outcome must say something
  // different when skipped, or the bot reports work it did not do. Only the
  // lines emitted AFTER each skip are examined: the prompts themselves
  // legitimately describe what would have happened.
  const skipAcknowledgement = (before: State, after: State) =>
    after.messages
      .slice(before.messages.length)
      .flatMap((m) => (m.from === 'bot' && m.kind === 'text' ? [m.text] : []))[0] ?? ''

  let state = toMedical()
  let before = state
  state = settle(skip(state))
  assert.equal(skipAcknowledgement(before, state), 'No problem.', 'nothing was attached')

  before = state
  state = settle(skip(state))
  assert.equal(skipAcknowledgement(before, state), 'That’s fine.', 'nothing was connected')

  state = settle(chooseOption(state, 'none'))
  before = state
  state = settle(skip(state))
  assert.equal(skipAcknowledgement(before, state), 'Understood.', 'nothing was filed')
  assert.equal(phaseOf(state), 'done')
})

test('reset clears every answer', () => {
  let state = settle(createState())
  state = settle(chooseOption(state, 'start'))
  state = settle(chooseOption(state, 'poor'))
  const fresh = createState()
  assert.deepEqual(fresh.answers, {})
  assert.deepEqual(fresh.messages, [])
})
