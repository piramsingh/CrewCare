# CrewCare — demo build

An exposure-awareness prototype for transit workers. One sign-in serves
everyone: the role is resolved from the account and the app routes itself —
workers into a mobile messaging portal, administrators into a desktop
dashboard. The UI never asks which one the person is.

**This is a demo.** There is no backend, no database, no authentication and no
messaging integration. Every figure is modeled, not measured.

```bash
npm install
npm run dev      # http://localhost:5173
npm test         # conversation machine, no browser needed
npm run build
```

Sign in with any ID. `W1042` lands on the worker path, `A0117` on the
dashboard; an empty field lands on the worker path.

## Running it

**The worker demo needs nothing but a browser:**

```bash
npm install
npm run dev          # http://localhost:5173
```

Sign in with `W4271` (worker) or `A6035` (admin). The worker path — sign-in,
channel choice, the whole simulated thread — runs entirely in the tab, with
no server and no network. A test asserts it issues zero off-origin requests.

**The admin dashboard needs the model API**, because its figures are real:

```bash
cd server
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn main:app --port 8000
```

It finds `admin_dashboard/admin_dashboard_model/` automatically in this repo;
set `ADMIN_MODEL_DIR` for other layouts. Without it the dashboard shows an
error and a Retry rather than inventing numbers.

## What is real and what is simulated

| Area | Status |
| --- | --- |
| Sign-in | Visual mock. Any input accepted, nothing validated or stored. |
| Role resolution | Simulated in `src/auth/roles.ts` — the one swap point for real auth. |
| Message thread | Simulated. No message is sent; iMessage and WhatsApp are visual skins only. |
| Health app | Simulated. Consent sheet is real and granular; no HealthKit/CommonHealth bridge exists in a browser. |
| Assignment | Read-only chrome. Hard-coded in `data/assignment.ts`; a read from the agency roster in production. |
| Medical records | Optional, real file picker. Nothing is read, parsed or sent; held in memory only. |
| Exposure figures | Illustrative, hard-coded in `src/data/mockExposure.ts`. |

## Data handling

These properties are load-bearing, not incidental:

- **Nothing leaves the tab.** No `localStorage`, `sessionStorage`, IndexedDB,
  cookies or network requests on either path. No webfont is linked, which is
  why Inter is used when present locally and falls back to the system stack.
- **Nothing is logged.** Health answers never reach the console.
- **Credentials are never held.** Both sign-in fields are uncontrolled. The
  employee ID is read once to resolve a role and cleared; the password field
  is never read at all.
- **The assignment is not collected and not editable.** The roster lives in
  the MTA's back end, so today's date, role and station sit in a strip at the
  top of the thread (`ThreadMeta`) rather than in the conversation. There is
  no confirm step and no correction form: offering one would imply the worker
  can change an agency record from a text thread.
- **Medical documents are the worker's alone.** The one file input in the app
  is the optional medical-records step. Attachments are in-memory object URLs,
  revoked on restart and unmount, never read, never parsed and never
  transmitted. They exist to shape that worker's own alerts and nothing else.
  The admin path has no import, prop or route that can reach them — the same
  structural guarantee that covers the intake answers.
- **The admin path cannot reach worker answers.** `screens/admin/*` imports
  from `data/mockExposure.ts`, `theme.ts` and presentational components only.
  There is no import, prop or route from the dashboard to conversation state —
  the intake is unreachable from the admin views, not merely hidden from them.
- **k-anonymity** (25 members) is applied inside `data/mockExposure.ts`, so a
  suppressed cell has nothing left in it for a view to leak.

## The operations dashboard

Reads live data through `server/ops/api.py`, which is a thin JSON layer over
the team's existing models in `admin_dashboard_model/`. The front end computes
no environmental value: it calls `conditions.score_stations()` — the same
function the Streamlit app uses — and renders the result.

```bash
# the models live beside crewcare/ in the repo; override for other checkouts
ADMIN_MODEL_DIR=../admin_dashboard_model ./.venv/bin/uvicorn main:app --port 8000
```

**Provenance is carried, not assumed.** The API labels every class of figure:
outdoor readings are `live` (Open-Meteo, no key, 3h disk cache), platform
PM2.5/temperature/humidity are `modelled` by `indoor.py` and `thermal.py`,
risk bands are `derived` by `risk.py`, and worker reports are `demo` — a
seeded corpus, not real MTA submissions. The UI shows `MODELLED` and `DEMO`
chips rather than presenting all four as equally real.

**Nothing is invented.** A metric the models cannot produce renders "No data".
If the API fails the dashboard shows the error and a Retry, and never falls
back to plausible numbers — there is a test that aborts every `/api/ops/`
request and asserts no figures appear.

**What is dynamic:** all four KPIs, the 496 map markers (real spine
coordinates, equirectangular projection, no tiles), the top-five ranking, the
station panel, and the concern breakdown. The time filter re-cuts everything
derived from worker reports; environmental readings are current-only and are
never re-cut to fake history.

**Known difference from the Figma:** "Stations with both signals" shows 87,
not 38. The models define no such metric, so it is computed from the card's
own subtitle — level ≥ 3 and at least one report in the window. The other
three KPIs match the Figma exactly because the Figma numbers were themselves
real output.

### Design notes

`A`-prefixed sign-ins land here. Built to the supplied design: stat row, live
risk map, station detail panel, top-five table, concern breakdown and a
placeholder for recommendations.

**The map is a proxy.** `RiskMap.tsx` draws the city as inline SVG rather
than loading map tiles — tiles mean a third-party request on every pan, and
the shape of the system is all this needs until the real geodata arrives.
Station pins are positioned as percentages, so swapping in projected
coordinates is a change to `mockOperations.ts`, not to the component.

**Risk bands and route bullets use official MTA colours** from the same
standard as the rest of the palette: green #009952, yellow #F6BC26, orange
#EB6800, red #D82233. Route bullets render dark text on yellow lines, because
the standard forbids white knock-out type on yellow.

**Worker reports appear here, and that is intended.** They are station
complaints — the one thing the worker flow deliberately sends outward —
carrying a station, a date and what was written. The privacy boundary is
unchanged: no health answer, no attachment, no health-app reading and no
employee id can reach this view, and the browser suite sweeps the rendered
DOM for all of them.

The k-anonymised exposure chart and table now live under **Risk Analytics**;
the other nav sections render an empty state.

**Dropped from the earlier dashboard:** the "Export report" modal, which the
supplied design does not include.

## Design system

Colours are the exact values from the MTA's official standard, **"MTA Brand
Colors / Subway, SIR & ADA" (rev. 2024-11-22)** — not the legacy Vignelli-era
line colours (`#0039A6` / `#FF6319`) quoted in the original brief, which are
the pre-refresh subway palette.

| Role | Token | Official value |
| --- | --- | --- |
| Chrome, primary actions | `cc-primary` | MTA Blue `#08179C` |
| Interactive accent | `cc-accent` | Blue `#0062CF` |
| Exposure indication **only** | `cc-exposure` | Orange `#EB6800` |
| Secondary text | `cc-grey` | Grey `#7C858C` |
| Page ground | `cc-ground` | `#F4F6FA` (neutral, not a brand colour) |

Two rules from the standard are honoured structurally: there is **one grey
only**, and yellow is unused, so *"do not use white knock-out type on yellow"*
cannot be broken by accident.

**Typeface: Helvetica**, the MTA's system typeface. It ships with macOS and
iOS and Arial substitutes metric-for-metric elsewhere, so no webfont is linked
and the demo still makes zero network requests.

Tokens are named for their **role**, not their hue, so the palette can be
swapped underneath without a name becoming a lie. `theme.ts` and the `@theme`
block in `index.css` are the only two places colour is defined — changing the
palette is an edit to those two blocks and nothing else.

Note: the MTA publishes a brand *colour and signage* standard, not an open web
component library. Colour and typography here are authoritative; layout and
components are this prototype's own, built to the Figma mockup.

## The agency logo

`src/assets/agency-mark.svg` is the MTA's current roundel (in use since 1994),
from [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:MTA_NYC_logo.svg).
It is used to match the approved Figma mockup. At 898 bytes Vite inlines it as
a data URI, so it costs no network request. Swapping it is a one-file change.

**Deployment constraint.** This prototype pairs an agency trademark with an
employee-credential field, which is the shape of a phishing page. What keeps it
on the right side of that line is that it is a local prototype which collects
nothing: the standing DEMO banner, the uncontrolled fields, the password that
is never read, and the absence of any network call. It must not be deployed
anywhere it could be mistaken for a real agency service, and the banner and
credential handling should not be weakened without revisiting this.

## Architecture

```
src/
  App.tsx                      routes on the resolved role
  auth/roles.ts                role resolution — swap point for real auth
  conversation/script.ts       questions, options, branching — data only
  conversation/machine.ts      pure state machine, no React, testable alone
  data/mockExposure.ts         admin mock data, k-anonymity applied
  screens/                     SignIn · worker/{ChannelSelect,MessageThread} · admin/*
  components/                  Bubble · QuickReplies · TypingIndicator ·
                               ThreadMeta · ProviderMark · Sheet · DemoBanner · DataNotice ·
                               PhoneFrame · AgencyMark
  theme.ts                     MTA design tokens + the two channel skins
```

`script.ts` is purely declarative — questions can be reworded, reordered or
rebranched there without touching the machine. `machine.ts` is pure functions
over a state object, which is why the whole flow is testable without rendering
anything (`test/machine.test.ts`).

**Editing the conversation:** add or change a `Step` in `script.ts`. `next`
sets the default successor, `branch` overrides it per option, `allowSkip` adds
a skip chip and `skipTo` sets where skipping goes. Stage B wording and option
sets are verbatim from the intake instrument and should not be paraphrased.

**Provider logos.** Apple Health uses the real icon, which Wikimedia Commons
carries as public domain (a simple geometric shape, below the threshold of
originality). CommonHealth has **no freely licensed logo**, so
`ProviderMark.tsx` draws a placeholder of our own — it is not The Commons
Project's artwork and should not be presented as it. Dropping in a supplied
file is a one-line change there.

## Filing a complaint

Stage F, after the alerts step, asks whether anything at a station should go
on record. This is **the one thing in the app intended to leave the worker's
phone** — everything else is theirs alone, and a complaint is the point of the
tool: it is how a condition becomes the local's problem instead of the
worker's.

It is one text box. The station and the date ride along from the roster and
the clock, so the only thing asked of the worker is the sentence nobody else
can write — a category picker would be asking them to do the filing system's
job at the end of a shift.

What it carries is fixed by the `Report` type and is exactly two fields:
station and what the worker wrote. There is no field, prop or code path by
which a health answer, an attachment or a health-app reading could join it. A
test asserts those two keys and nothing more. The box says so before it is
submitted, and the acknowledgement says so again.

It is offered on **both** paths out of the alerts step. Declining the texts
must not cost someone the ability to report a hazard.

Nothing is transmitted in this demo, as the standing notice says; the copy
describes what the real thing would send.

**Sheets.** The complaint form and the health-app consent sheet both render
through `components/Sheet.tsx`: a dimmed scrim over the thread, a slide-up,
a grabber, and `aria-modal`. The scrim is not decoration — without it a bottom
panel reads as more page rather than as something waiting on you, and tapping
away is what people try before hunting for Cancel. It is scoped to the phone
frame so the demo chrome around the device stays undimmed.

## Acknowledgements and skipping

A step's `ack` fires when it is answered. Steps whose acknowledgement
describes an outcome — "Filed.", "Connected.", "That stays on your phone." —
must also declare a `skipAck`, because skipping means the outcome did not
happen. Without it the bot reports work it never did. A test asserts the
acknowledgement emitted after each skippable action step.

## Going back

A quick reply is one tap and the thread is append-only, so a mistap would
otherwise be permanent. A **Back** control sits above the composer whenever
there is an answer to take back.

`machine.ts` keeps a stack of snapshots, each taken immediately before an
answer is recorded — the exact state in which the question was on screen and
unanswered. Going back restores one: the worker's reply and everything the bot
said after it leave the transcript, the question is live again, and the
recorded answer is gone. Repeating walks back one answer at a time until the
start, where the control disappears.

Consequences that fall out of restoring whole states, rather than being
special-cased:

- Backing out of the Q2 symptom branch discards Q3–Q5 along with it, because
  those answers were never in the restored snapshot.
- Taking back an attachment removes it from state, and the thread revokes the
  orphaned object URL.
- Taking back a filed complaint un-files it and does not reopen the form.
- Taking back a health-app grant withdraws it and does not reopen the consent
  sheet — the sheets snapshot the step behind them, not themselves.
- Back is offered at Stage E too, so the last answer can be changed from the
  summary.

There is deliberately no redo: nothing that was taken back is retained.

## Conversation rules

The bot acknowledges health answers neutrally ("Got it.") and moves on. It
never presses for an answer, never follows up on a symptom and never
interprets or comments on one. Every health question can be skipped. Q2
branches: *No* or *Prefer not to say* skips the symptom questions entirely;
declining Q2 is treated the same way.

Declining the shift alerts ends the conversation on a different branch from
accepting it: no sample alert, no "you're all set", and no STOP instructions
for a subscription that was never created — just an acknowledgement and a way
back in. `test/machine.test.ts` guards this in both directions.

Stage C2 offers to accept a doctor's note or test results as a PDF or image.
It is optional, says what happens to the file before asking for it, and
skipping it changes nothing downstream. Anything attached is acknowledged by
filename and never interpreted, exactly as health answers are.

The copy deliberately never mentions the dashboard, reports or aggregation.
Those are the local's concerns, not the worker's, and naming them here would
introduce a thing the worker otherwise has no reason to think about. What the
worker is told is the part that affects them: it stays on their phone, it only
changes what gets texted to them, and nobody else sees it. A test asserts the
absence of that vocabulary, so it cannot creep back in.

Stage C3 offers a health-app connection, and is the one place the two
channels differ. An iMessage thread means an iPhone, so it asks only about
Apple Health; WhatsApp is cross-platform, so it offers Apple Health or
CommonHealth. Offering an Android-only provider to an iPhone would be
offering something that cannot work. `script.ts` expresses this as a
`byChannel` override on that step alone, and a test asserts the two
transcripts are otherwise identical. Picking a provider
grants nothing — it opens a consent sheet listing each data type
individually, and only the types still switched on when Allow is pressed are
granted. Backing out leaves the worker on the step; granting nothing is not
treated as a connection. What is recorded is the grant itself, never health
data: there is no HealthKit bridge in a browser and the demo makes no network
calls.

The three sharing tiers escalate deliberately — the schedule is already known,
documents are sent, health data is connected — and each one is refusable on
its own without affecting the others.

The worker's role and station never appear in the conversation at all. They
are standing context — the agency's record, not an answer — so they live in
the chrome, where they stay visible while the worker scrolls and cost neither
a turn nor a tap. `data/assignment.ts` holds them; a test asserts they reach
neither the transcript nor the closing summary.

## Notes for production

- **A health-app connection would need a native app.** Apple Health is reachable only
  through HealthKit in a native iOS app, and CommonHealth through its Android
  SDK. Neither can be reached from a web page or from a messaging thread, so
  in production Stage C3 hands off to a companion app and returns. The consent
  sheet's shape — per-type, refusable, revocable at the provider — is what
  HealthKit requires, and is worth preserving in whatever replaces it.
- **iMessage is a skin, not a path.** iMessage has no inbound bot API, and
  Apple Messages for Business requires brand registration this use case would
  not obtain. **WhatsApp Business API is the buildable production path.**
- **The agency roundel is a trademark.** It is used here to match the approved
  design, but pairing it with an employee-credential field reads as a phishing
  page — see "The agency logo" for the deployment constraint that follows.
- **Orange means exposure.** It is used for exposure indication and the demo
  banner's rule, and never as decoration.
- The dashboard is a desk tool: fixed to a 1280px minimum and deliberately not
  responsive to phone widths.
- Real auth replaces the body of `resolveRole`. Nothing else needs to change.
