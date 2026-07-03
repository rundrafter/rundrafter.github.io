# RunDrafter intake form — build spec

The static, client-side intake form (phase 2 of RunDrafter). It collects a
runner's details in the browser, assembles them into an `intake.json`,
validates that file against the authoritative schema, and hands it back to the
pipeline operator: the runner downloads the file and clicks one button that
opens a prefilled email to attach it to. No backend — the pipeline is run
manually (phase 1).

This spec is the contract, the decisions, and the ordered build plan. It is
written so a fresh contributor (or agent) can implement it without re-deriving
context. Tick the checklist at the foot in the commit that does each task.

---

## Source of truth

The form depends on `run-drafter` **only** through the intake contract. These
upstream files are authoritative; this repo vendors copies but never forks the
contract:

- `run-drafter/docs/intake-schema.json` — the schema the output must validate
  against (schema_version `"1"`).
- `run-drafter/docs/intake-example.json` — golden example; authoritative for
  *shape*, and its values are the reference our fixtures reproduce.
- `run-drafter/docs/intake.md` — field-by-field reference, including the
  intended form input type for every field. **Build the form from this doc.**

If the form and the schema ever disagree, the schema wins and this spec is
wrong — fix the spec.

---

## Resolved decisions

Non-obvious decisions made up front. Each is recorded as an ADR in
`docs/decisions/` — the ADR holds the *why* and the rejected alternatives; the
one-liners below are the decision the rest of this spec builds on.

1. **Vanilla runtime, no build step** — plain hand-authored HTML/CSS/JS served
   as-is; node only in dev/CI tooling, never in the shipped page.
   ([ADR 001](../decisions/001-vanilla-no-build-step.md))
2. **Validate against the real schema, client-side, before handoff** — vendored
   schema + Ajv in the browser; an invalid object blocks the download.
   ([ADR 002](../decisions/002-client-side-schema-validation.md))
3. **Uniform email handoff: download + prefilled `mailto:`** — the same
   download-then-attach flow on every device; no Web Share, no JSON in the body.
   ([ADR 003](../decisions/003-uniform-mailto-handoff.md))
4. **Host as an org GitHub Pages site at the root URL** — `<org>.github.io`
   (e.g. `run-drafter`), not a project-path or custom-domain site.
   ([ADR 004](../decisions/004-org-pages-root-hosting.md))

**Flag carried from ADR 001:** node-in-CI for tests is the one place the
runtime's no-toolchain rule admits tooling (see "Testing"). If even that is
unwanted, say so and we lean on upstream schema tests + manual QA instead.

---

## What the form collects

Drive every field, input type, label, and enum from `run-drafter/docs/intake.md`.
Summary of the intake object's top level (see the schema for exact types):

| Section           | Required? | Notes                                                                                                    |
| ----------------- | --------- | -------------------------------------------------------------------------------------------------------- |
| `meta`            | system    | `schema_version: "1"`, `submitted_at` (ISO 8601) set at handoff time — not a form field                  |
| `units`           | yes       | radio km/mi; controls distance labels, does **not** convert values                                       |
| `runner`          | optional  | name, age, sex, experience                                                                               |
| `goal`            | yes       | race, distance, date, target_time, start_date                                                            |
| `recent_result`   | yes       | distance, time, date                                                                                     |
| `current_fitness` | yes       | weekly_distance, longest_run, recent_peak_weekly (opt)                                                   |
| `weekly_schedule` | yes       | days_available, long_run_day, rest_days (multi), preferred_sessions (repeating)                          |
| `strength_cross`  | optional  | strength_per_week, strength_days, strength_type, warmup_jog, cross_training{type,frequency}              |
| `preferences`     | yes       | calibrate_to (radio), build_mode (opt radio, default standard)                                           |
| `injuries`        | optional  | repeating: area, status, notes                                                                           |
| `health_screen`   | yes       | 8 PAR-Q booleans + other_reason (opt)                                                                    |
| `consent`         | yes       | disclaimer_accepted (req), health_acknowledged (conditional), terms_accepted (opt), accepted_at (system) |
| `b_races`         | optional  | repeating (≤3): name, distance, date, target_time                                                        |
| `other_events`    | optional  | repeating: name, distance, date                                                                          |
| `notes`           | optional  | other (textarea)                                                                                         |
| `output`          | yes       | formats (checkboxes: spreadsheet/pdf), tracking (checkbox)                                               |

`progress` exists in the schema for phase-3 re-planning and is **not** collected
by this form.

---

## Rules the schema can't express (enforce in JS)

The schema validates types/enums/patterns. These product rules are enforced by
the assembler/validator and block handoff with a clear message:

- **Empty-object pruning.** Never emit an optional section as an empty or
  partial object. If the runner leaves `runner`, `strength_cross`,
  `cross_training`, `injuries`, `b_races`, `other_events`, or `notes` blank,
  omit the key entirely — an empty `{}` can violate `required`/
  `additionalProperties`.
- **Health screen → consent gate.** If any `health_screen` flag is `true`, show
  the medical-clearance warning and require `consent.health_acknowledged === true`
  before handoff.
- **Disclaimer gate.** `consent.disclaimer_accepted` must be `true` to hand off.
- **Date ordering.** `goal.start_date ≤ goal.date`; every `b_races[].date` and
  `other_events[].date` must be before `goal.date`.
- **At least one output format.** `output.formats` must be non-empty.
- **Timestamps.** Set `meta.submitted_at` and `consent.accepted_at` (ISO 8601)
  at the moment of handoff, not earlier.
- **Advisory consistency.** `strength_days` / `rest_days` / `days_available`
  "should be consistent" — warn, don't block.

---

## Architecture and file layout

```text
index.html                  # the form, semantic sections, no inline logic
assets/
  styles.css                # responsive, theme-aware, accessible labels
  form.js                   # DOM wiring: render sections, repeating add/remove,
                            #   conditional consent, gather form-state
  assemble.js               # PURE ES module: formState -> intake object, with
                            #   pruning + cross-field validation (returns errors)
  handoff.js                # build the intake.json File; download + compose the
                            #   prefilled mailto (recipient/subject/body)
  schema.js                 # vendored schema as an ES module (works from file://)
  ajv.bundle.js             # vendored Ajv standalone browser build (pinned)
schema/
  intake-schema.json        # vendored mirror (source for schema.js + tests)
  intake-example.json       # vendored golden example
  SOURCE.md                 # upstream path + pinned run-drafter revision
scripts/
  sync_contract.py          # copy schema+example from upstream; regen schema.js
tests/
  fixtures/                 # form-state fixtures + expected intake objects
  assemble.test.mjs         # node+Ajv: assembler output validates vs schema
.github/workflows/ci.yml    # run tests + contract drift check
justfile                    # + sync-contract, serve, test targets
```

**Keep `assemble.js` a pure, import-clean module** (no DOM, no side effects):
input a plain form-state object, return `{ intake, errors }`. That is what makes
it unit-testable in node with the same Ajv + schema the browser uses — highest
fidelity. `form.js` owns DOM/browser concerns; `handoff.js` owns the
file/download/mailto concerns.

### Contract sync mechanism

`scripts/sync_contract.py` is the only thing that writes `schema/*` and
`assets/schema.js`, so drift is a one-command fix. Run via `uv run python
scripts/sync_contract.py` (see `.fieldkit/conventions/python/run.md`) — this is
dev/CI tooling only, per ADR 001; nothing it produces ships an interpreter or a
build step, only static JSON/JS files:

1. Copy `intake-schema.json` and `intake-example.json` from the upstream source
   — locally from the sibling checkout (`../run-drafter/docs/`), or in CI from
   GitHub raw at the pinned revision in `schema/SOURCE.md`.
2. Regenerate `assets/schema.js` by wrapping the JSON as
   `export default <json>;`. Inlining as a module means the page needs no
   `fetch`, so validation works from `file://` too.
3. Record the upstream commit SHA in `schema/SOURCE.md`.

CI runs the sync into a temp dir and diffs against the committed copies; a
mismatch fails the build with "contract drift — run `just sync-contract`".

### Validation and handoff at runtime

On submit, `form.js` gathers form-state → `assemble.js` returns
`{ intake, errors }` (cross-field errors) → if none, Ajv (from
`ajv.bundle.js`) validates `intake` against `schema.js`. Only a clean pass
enables handoff. `handoff.js` then, identically on every device:

1. Downloads `intake.json` (Blob + object URL) from the validated object.
2. Shows a success screen with an **Email it in** button that opens a prefilled
   `mailto:` — recipient = the return address; subject composed from
   `runner.name` + `goal.race` (e.g. "RunDrafter intake — Alex Smith, Melbourne
   Marathon"); body a basic message asking the runner to attach the
   `intake.json` they just downloaded.
3. Also shows the return address as plain text and a **Download again** link, so
   the flow is recoverable if the download or mail app misbehaves.

Ajv errors and cross-field errors render inline against their fields.

---

## Testing

Runtime is zero-toolchain; **tests may use node in dev/CI** (it ships nothing).
Chosen because a node test can import `assemble.js` and validate its output with
the *same* Ajv + vendored schema the browser uses — no second validator to keep
honest. `handoff.js`'s download/mailto is browser-only and is covered by manual
QA (and the optional Playwright smoke test), not node.

- **Assembler unit tests** (`tests/assemble.test.mjs`): feed form-state fixtures,
  assert the assembled object validates against the vendored schema, and assert
  each cross-field rule (pruning, health gate, date ordering, ≥1 format) fires.
- **Golden reproduction:** a fixture reproduces `schema/intake-example.json`'s
  structure from a plausible form-state, proving the form can emit the reference
  shape.
- **Contract drift check** (CI): committed `schema/*` matches a fresh sync.
- **Deferred / optional:** one Playwright smoke test (fill DOM → download →
  validate) once the form stabilises. Not in the walking skeleton.

Run the narrow test while iterating; widen to the full file before done.

---

## Build plan (walking-skeleton first)

Each task has a definition-of-done. Build order is not feature order: get one
thin path running end to end, then layer.

- **T0 — Tooling + vendored contract.** `scripts/sync_contract.py`, `schema/*`,
  `assets/schema.js`, justfile `sync-contract`/`serve`/`test` targets, CI
  skeleton. *DoD:* `just sync-contract` produces the vendored files; a stub test
  asserts the vendored example validates against the vendored schema (green).
- **T1 — Walking skeleton.** `index.html` with only the required sections'
  minimal fields, `assemble.js` producing a valid intake, Ajv gating a plain
  download. *DoD:* hand-fill the minimal required fields in a browser →
  downloaded `intake.json` validates against the schema.
- **T2 — Required sections complete.** All required fields with correct input
  types, unit-aware labels, `weekly_schedule` multi-select + `preferred_sessions`
  repeating. *DoD:* reproduces the required portion of the example.
- **T3 — Optional sections + pruning.** runner, strength_cross (+cross_training),
  injuries, b_races, other_events, notes; blank sections omit their keys.
  *DoD:* filled → matches `intake-example.json` structure; blank → keys absent.
- **T4 — Cross-field + conditional logic.** health-screen→consent gate, date
  ordering, disclaimer gate, ≥1 output format, timestamps at handoff.
  *DoD:* each rule covered by a test.
- **T5 — Test suite + fixtures.** `tests/assemble.test.mjs` + fixtures; CI runs
  tests + drift check. *DoD:* `just test` and CI green.
- **T6 — Email handoff + success screen.** `handoff.js`: download + prefilled
  mailto, composed subject/message, return address text, download-again link.
  *DoD:* a valid submission downloads the file and opens a correctly prefilled
  email, identically across browsers.
- **T7 — Styling + UX.** Responsive, theme-aware, accessible labels, inline
  error surfacing. *DoD:* usable on mobile; errors legible.
- **T8 — README + docs.** ADRs 001–004 (stack / validation / handoff / hosting)
  and their register are written; update `README.md` local-dev + contract-sync
  instructions, and revisit each ADR's "Consequences" against what was actually
  built. *DoD:* docs match the code.
- **T9 — Deploy (see Manual steps).** *DoD:* form live at `<org>.github.io`.

---

## Manual steps (human-only — I can't do these)

These need you; the build tasks above don't block on them except T9.

1. **Return email address + next-steps copy.** The address the runner sends
   `intake.json` to — it powers the `mailto:` recipient and the on-screen/README
   text. Needed for T6. *(Blocking content decision.)*
2. **Disclaimer + PAR-Q acknowledgement wording.** Exact text for
   `consent.disclaimer_accepted` and the health-screen warning ("training
   guidance, not medical advice…"). Legal-ish copy — your call. Needed for T4/T6.
3. **Create the GitHub org** (`run-drafter`, or `rundrafter` if taken). Account/
   org creation is human-only.
4. **Transfer + rename this repo** to `<org>/<org>.github.io` so its root serves
   the site. (The local `.fieldkit` symlink is an absolute local path and is
   unaffected.)
5. **Enable GitHub Pages** — Settings → Pages → source `main` / root — and
   confirm the live URL.
6. **Confirm node-in-CI is acceptable** for tests (or veto it; see Testing).
7. *(Optional, later)* register a custom domain if you outgrow the
   `github.io` URL.

---

## Progress

- [x] T0 — Tooling + vendored contract
- [ ] T1 — Walking skeleton (end-to-end valid download)
- [ ] T2 — Required sections complete
- [ ] T3 — Optional sections + pruning
- [ ] T4 — Cross-field + conditional logic
- [ ] T5 — Test suite + fixtures
- [ ] T6 — Email handoff + success screen
- [ ] T7 — Styling + UX
- [ ] T8 — ADRs + README
- [ ] T9 — Deploy to `<org>.github.io`
