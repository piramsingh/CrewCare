# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Static HTML/CSS, single self-contained file, served from `docs/` by GitHub Pages at `piramsingh.github.io/CrewCare`. No build step. Chosen by the user for the landing surface; the product app itself is React + Vite (`crewcare/`) with a FastAPI service (`crewcare/server/`) and is unaffected by this choice.

## Users

**Primary (landing surface): transit union health-and-safety representatives.** A rep at a local such as TWU Local 100 evaluating whether a tool is safe to put in front of members. Their first question is not "is this impressive" but "what does this expose about my members, and what does it give me." They are not necessarily technical.

**Primary (product): NYC transit workers.** On shift, often underground, frequently at the end of a tour. They do not install anything — the entire worker experience happens in a text thread.

**Secondary (product): the union local.** Receives aggregate exposure and complaint patterns through a dashboard.

## Product Purpose

Give transit workers exposure awareness for the station they are working today, a private way to record their own health, and a route to put a station problem on record with their local — without their health information ever reaching the local or the employer.

Success is a worker filing a complaint they would otherwise have swallowed, and a rep acting on a station rather than an anecdote.

## Positioning

**The data boundary is the product, not a setting.** Health answers, attached medical records and connected Apple Health data stay on the worker's device and shape only the alerts that worker receives. The single thing that deliberately leaves the phone is a complaint the worker chooses to file, carrying station, date and what they wrote — never a health answer, an attachment, or a health-app reading. The product states this boundary in its own confirmation copy rather than burying it in a policy.

A second, weaker differentiator: no per-station air-quality feed exists for the NYC subway, so platform conditions are physically modelled from live street-level readings rather than asserted.

## Operating Context

- The worker path runs entirely in a messaging thread (iMessage or WhatsApp skins). No app install, no account.
- Alerts are sent once per shift, roughly 90 minutes before the worker reports.
- Complaints are filed at the end of a tour, so the flow asks for one sentence rather than a category taxonomy.
- The rep-facing dashboard is a desktop surface reviewed away from the platform.
- Evaluation context for the landing page: a rep or organiser opening a link from LinkedIn, likely on a phone, with no prior knowledge of the project.

## Capabilities and Constraints

**Built and working:** worker messaging flow (health questionnaire, optional medical-record attach, optional Apple Health connect with per-scope consent, notification opt-in, station complaint); operations dashboard over a JSON API; physical exposure models covering all 496 NYC subway stations (PM2.5, temperature, humidity, heat index, mould risk, a 1–5 risk level).

**Explicitly not built:** real authentication, live messaging integration, and the Apple Health bridge (which requires a native iOS app using HealthKit — unreachable from a web page or a messaging thread). The demo simulates these end to end.

**Modelled, not measured:** every platform figure. These are a prior for where to look first, never a clearance that a station is safe. This caveat must appear wherever a figure appears.

**Simulated:** the 449 worker complaints shipped in `datasets/worker_complaints.csv` are a synthetic corpus, not real submissions.

**Terminology:** "local" (not "agency" or "employer") for the union; "members" when addressing a union audience, "workers" otherwise; "tour" for a shift.

## Brand Commitments

- Name **CrewCare**; tagline **"Safer Work. Stronger Transit."**
- Palette is the MTA published brand standard, encoded in `crewcare/src/theme.ts`: `#08179C` primary, `#0062CF` accent, `#F4F6FA` ground, `#7C858C` grey, `#EB6800` Signal Orange.
- **Signal Orange is exposure indication only, never decoration.** This is the product's own standing rule and carries to every surface.
- **No MTA logo, wordmark or roundel may be used.** `crewcare/src/assets/agency-mark.svg` is the MTA roundel and is out of bounds for any public-facing surface.
- **"Independent student prototype · Not affiliated with the MTA" must be visible**, not buried. Framing the work as an agency tool without that line would misrepresent it.
- Voice: plain, specific, and willing to state its own limits. The product's confirmation copy is the model.

## Evidence on Hand

- `docs/crewcare-demo.mp4` — 23s demo of the real flow, with audio. Also `docs/crewcare-demo.gif` (520px, autoplaying) and `docs/crewcare-poster.jpg`.
- Public repository: `github.com/piramsingh/CrewCare`.
- `admin_dashboard/admin_dashboard_model/METHODOLOGY.md` — every formula, constant and stated limitation.
- Real product copy in `crewcare/src/conversation/script.ts`, usable verbatim.
- Live figures the API returns today: 496 stations monitored, 46 high-risk platforms, 233 reports in 30 days, 87 stations where model and reports agree; concern split 30% dust/air, 30% heat, 12% damp/mould, 12% ventilation.
- Built at a Cornell climate hackathon over the weekend of 19–20 September 2026 by a team credited as "paass". **Exact event name and teammate names are not yet confirmed and must not be invented.**

**Absences that must not be fabricated:** no pilot, no deployment, no union partnership, no endorsement, no users, no testimonials, no press, no funding, no pricing. There is no contact email or form for this surface — the user chose the repository as the destination instead.

## Product Principles

1. **State the boundary before the benefit.** For this audience, what the tool does *not* collect is more persuasive than what it does.
2. **Quote the product, don't paraphrase it.** The in-product copy is plainer and more credible than any marketing rewrite of it.
3. **Volunteer the limits.** Labelling figures as modelled and reports as simulated is what makes everything else believable.
4. **Plain language over precision theatre.** A rep who is not technical must be able to follow the whole thing.
5. **Never imply a relationship that does not exist** — with the MTA, a local, or any employer.

## Accessibility & Inclusion

- WCAG AA contrast is a floor, not a goal: the brand grey `#7C858C` fails as small text on light grounds and must be darkened for body copy (`#667079` or darker verified against its actual ground).
- Content must be legible on a phone in poor conditions — this audience reads on transit, often one-handed.
- Motion must respect `prefers-reduced-motion`.
- The demo video carries meaning, so the page must convey that meaning in text as well; the video is never the only carrier of a claim.
