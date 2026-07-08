# rundrafter-webform — architecture

The static, client-side intake form (phase 2 of RunDrafter). It collects a
runner's details in the browser, assembles them into an `intake.json`,
validates that file against the authoritative schema, and hands it back to
the pipeline operator: the runner downloads the file and clicks one button
that opens a prefilled email to attach it to. No backend — the pipeline is
run manually (phase 1).

This is the living reference for how the form is built and what it enforces.
For *why* the non-obvious choices were made, see the ADRs in
[`docs/decisions/`](decisions/); for setup and local dev, see the
[README](../README.md).

---

## Source of truth

The form depends on `rundrafter` **only** through the intake contract. These
upstream files are authoritative; this repo vendors copies but never forks
the contract:

- `rundrafter/docs/intake-schema.json` — the schema the output must validate
  against (schema_version `"1"`).
- `rundrafter/docs/intake-example.json` — golden example; authoritative for
  *shape*, and its values are the reference our fixtures reproduce.
- `rundrafter/docs/intake.md` — field-by-field reference, including the
  intended form input type for every field.
- `rundrafter/docs/spec/contracts.md` — the `intake.json` contract table plus
  the stage-1 tripwire note; authoritative for the cross-field *constraints*
  (date ordering, event windows, schedule rules) the schema alone can't
  express.
- `rundrafter/src/rundrafter/validate.py` — stage 1's actual implementation
  of those cross-field rules; authoritative for exact semantics (strict vs.
  non-strict comparisons, error codes) whenever `contracts.md`'s prose is
  ambiguous.

If the form ever disagrees with the schema or these cross-field rules,
upstream wins and this doc is wrong — fix this doc.

---

## What the form collects

Summary of the intake object's top level (see the schema for exact types):

| Section           | Required? | Notes                                                                                                                                                                                                                      |
| ----------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `meta`            | system    | `schema_version: "1"`, `submitted_at` (ISO 8601) set at handoff time — not a form field                                                                                                                                    |
| `units`           | yes       | radio km/mi; controls distance labels, does **not** convert values                                                                                                                                                         |
| `runner`          | yes       | name (req), age (opt), experience (req) — no `sex` field                                                                                                                                                                   |
| `goal`            | yes       | race, distance, date, target_time, start_date                                                                                                                                                                              |
| `recent_result`   | yes       | distance, time, date                                                                                                                                                                                                       |
| `current_fitness` | yes       | weekly_distance, longest_run, recent_peak_weekly (opt)                                                                                                                                                                     |
| `weekly_schedule` | optional  | availability grid (morning/evening per weekday, all ticked by default), long_run_day (opt override), rest_days (opt override, multi), preferred_sessions (repeating) — absent entirely leaves the schedule to the resolver |
| `strength_cross`  | optional  | strength_per_week, strength_days, strength_type, warmup_jog, cross_training{type,frequency}                                                                                                                                |
| `preferences`     | optional  | calibrate_to (radio, default "Let RunDrafter decide"), build_mode (radio, default "Let RunDrafter decide")                                                                                                                 |
| `injuries`        | optional  | repeating: area, status, notes                                                                                                                                                                                             |
| `consent`         | yes       | disclaimer_accepted (req), terms_accepted (opt), accepted_at (system)                                                                                                                                                      |
| `b_races`         | optional  | repeating (≤3): name, distance, date, target_time                                                                                                                                                                          |
| `other_events`    | optional  | repeating: name, distance, date                                                                                                                                                                                            |
| `notes`           | optional  | other (textarea)                                                                                                                                                                                                           |
| `output`          | optional  | formats (checkboxes: spreadsheet/pdf; both unticked = let RunDrafter decide) — `tracking` is gone, the spreadsheet always carries an Actual column                                                                         |

`progress` exists in the schema for phase-3 re-planning and is **not**
collected by this form.

Every optional section above is sparse by construction: `assemble.js` omits
it entirely rather than emitting an empty or partial object when the runner
leaves it on "Let RunDrafter decide" (see `pruneWeeklySchedule` /
`pruneOptionalObject` in `assets/assemble.js`).

---

## Rules the schema can't express (enforced in JS)

The schema validates types/enums/patterns. These product rules are enforced
by the assembler/validator; `assemble()` returns `{ intake, errors, warnings }`
— a non-empty `errors` blocks handoff with a clear message, `warnings`
surface as a non-blocking notice. The rules mirror `rundrafter`'s stage 1
(`validate.py` / `contracts.md`) rule-for-rule, so an intake this form
accepts never bounces back from the pipeline.

### Blocking (`errors`)

- **Empty-object pruning.** Never emit an optional section as an empty or
  partial object. If the runner leaves `runner`, `strength_cross`,
  `cross_training`, `injuries`, `b_races`, `other_events`, or `notes` blank,
  omit the key entirely — an empty `{}` can violate `required`/
  `additionalProperties`.
- **Disclaimer gate.** `consent.disclaimer_accepted` must be `true` to hand
  off.
- **Date ordering** (mirrors `_validate_date_ordering`):
  - `goal.start_date` strictly `<` `goal.date` (`DATE_ORDER_START_AFTER_GOAL`).
  - `recent_result.date` `≤` `goal.start_date` (`DATE_ORDER_RESULT_AFTER_START`).
  - Every `b_races[].date` and `other_events[].date` strictly between
    `goal.start_date` and `goal.date` (`DATE_OUT_OF_WINDOW`).
  - No two events, across `b_races` and `other_events` combined, share a date
    (`DUPLICATE_EVENT_DATE`).
- **Schedule** (mirrors `_validate_schedule`, checked only against the
  *explicit overrides* the runner gave — `days_available` isn't a raw-intake
  field any more, so there's nothing to check pre-resolution):
  - `weekly_schedule.long_run_day` must not be in `rest_days`
    (`LONG_RUN_DAY_IS_REST`).
  - No `preferred_sessions[].day` falls on a rest day
    (`PREFERRED_SESSION_ON_REST_DAY`).
  - A `preferred_sessions[]` entry needs both `distance` and `effort` to
    become an anchor session — one without the other blocks with a message
    naming the row (schema-level `dependentRequired`, given a friendly
    message here rather than a raw Ajv error).
  - A day whose grid has both halves unticked (see `pruneAvailability`'s
    "absent = available" default) is never a running day; unlike a
    trainable-day *count*, the grid expresses this directly, so it's
    checked against every explicit override:
    - `weekly_schedule.long_run_day` must not be a fully-unticked day
      (`LONG_RUN_DAY_UNAVAILABLE`).
    - An explicit `rest_days` override must cover every fully-unticked day
      (`REST_DAYS_OMIT_UNAVAILABLE_DAY`).
    - No `preferred_sessions[].day` falls on a fully-unticked day
      (`PREFERRED_SESSION_ON_UNAVAILABLE_DAY`).
- **Timestamps.** Set `meta.submitted_at` and `consent.accepted_at`
  (ISO 8601) at the moment of handoff, not earlier.

An empty `weekly_schedule.rest_days` override, or both `output.formats`
checkboxes left unticked, are **not** errors — they're pruned to "absent"
(see empty-object/array pruning above) and mean "let RunDrafter decide".
Neither `weekly_schedule.days_available ≥ 3` nor a required `output.formats`
are enforced here any more: the availability grid can't express a trainable-
day count directly, so an under-constrained grid is instead a **resolver**-side
warning (`SCHEDULE_UNDER_CONSTRAINED` in `validate.py`) this form generally
can't check without running the resolver — except the over-constrained-grid
case below, which is form-checkable.

### Non-blocking (`warnings`)

- **Stale recent result.** `recent_result.date` more than 183 days before
  `goal.start_date` (`RECENT_RESULT_OLD`) — VDOT-derived paces may not
  reflect current fitness.
- **Over-constrained availability grid.** 5 or more days with both halves
  unticked leaves at most 2 possibly-trainable days a week, guaranteeing
  fewer than the resolver's 3-day minimum no matter which rest days it picks
  (mirrors `SCHEDULE_UNDER_CONSTRAINED` in `validate.py`, warning-level parity
  only — a looser grid may still end up under-constrained once the resolver
  adds rest days, but that isn't form-checkable).

Before changing any of these rules, or after any contract sync
(`just sync-contract`), diff `assets/assemble.js` against the sibling
`rundrafter` checkout's `validate.py` + `docs/spec/contracts.md`, run
`tests/test_stage1_parity.py`, and if the rules changed, re-pin with
`uv run python scripts/sync_contract.py --update-rules-revision`. This
validation drifted silently from upstream once already (pre-deploy audit,
2026); the parity test and the `rules_revision` hash pin in
`schema/SOURCE.md` exist to catch it happening again.

---

## Architecture and file layout

```text
index.html                  # the form, semantic sections, no inline logic
assets/
  styles.css                # responsive, theme-aware, accessible labels
  form.js                   # DOM wiring: render sections, repeating add/remove,
                            #   conditional consent, gather form-state
  assemble.js               # PURE ES module: formState -> intake object, with
                            #   pruning + cross-field validation (returns
                            #   errors + warnings)
  handoff.js                # build the intake.json File; download + compose the
                            #   prefilled mailto (recipient/subject/body)
  schema.js                 # vendored schema as an ES module (works from file://)
  ajv.bundle.js              # vendored Ajv standalone browser build (pinned,
                            #   fetched by URL and committed by hand)
schema/
  intake-schema.json        # vendored mirror (source for schema.js + tests)
  intake-example.json       # vendored golden example
  SOURCE.md                 # upstream path + pinned rundrafter revision
scripts/
  sync_contract.py          # copy schema+example from upstream; regen schema.js
tests/
  fixtures/                 # form-state fixtures + expected intake objects
  test_assemble.py          # pytest+Playwright: drives index.html in a real
                            #   browser, feeds form-state, asserts the
                            #   assembled/downloaded object validates vs schema
.github/workflows/ci.yml    # run tests + contract drift check
justfile                    # + sync-contract, serve, test targets
```

**Keep `assemble.js` a pure, import-clean module** (no DOM, no side effects):
input a plain form-state object, return `{ intake, errors, warnings }`. That
is what makes it easy to drive directly from a Playwright test with the same
Ajv + schema the browser uses — highest fidelity. `form.js` owns DOM/browser
concerns; `handoff.js` owns the file/download/mailto concerns.

### Contract sync mechanism

`scripts/sync_contract.py` is the only thing that writes `schema/*` and
`assets/schema.js`, so drift is a one-command fix. Run via `uv run python
scripts/sync_contract.py` (see `.fieldkit/conventions/python/run.md`) — this
is dev/CI tooling only, per ADR 001; nothing it produces ships an
interpreter or a build step, only static JSON/JS files:

1. Copy `intake-schema.json` and `intake-example.json` from the upstream
   source — locally from the sibling checkout (`../rundrafter/docs/`), or
   in CI from GitHub raw at the pinned revision in `schema/SOURCE.md`.
2. Regenerate `assets/schema.js` by wrapping the JSON as
   `export default <json>;`. Inlining as a module means the page needs no
   `fetch`, so validation works from `file://` too.
3. Record the upstream commit SHA in `schema/SOURCE.md`.

CI runs the sync into a temp dir and diffs against the committed copies; a
mismatch fails the build with "contract drift — run `just sync-contract`".
(The CI job itself is currently disabled — `rundrafter` is private and the
job's unauthenticated `raw.githubusercontent.com` fetch 404s; restoring it
needs a scoped PAT, tracked separately.)

`schema/SOURCE.md` also pins a separate `rules_revision`: the upstream hash
of `validate.py` + `contracts.md` at the last cross-field parity review.
These aren't vendored files, so `just check-contract` only compares hashes
— against the sibling checkout, locally; it's a no-op without one — and
reports "rules changed upstream since last parity sync" rather than diffing
content. Re-pin after syncing `assemble.js` to a rule change with
`uv run python scripts/sync_contract.py --update-rules-revision`.
`tests/test_stage1_parity.py` is the executable half of the same guard: it
pipes every intake this suite considers valid through the sibling's real
`rundrafter validate` CLI (skipped without the sibling).

### Validation and handoff at runtime

On submit, `form.js` gathers form-state → `assemble.js` returns
`{ intake, errors, warnings }` (cross-field errors + non-blocking advisories)
→ if `errors` is empty, Ajv (from `ajv.bundle.js`) validates `intake`
against `schema.js`. Only a clean pass enables handoff; any `warnings`
render as a non-blocking notice alongside the download, never in place of
it. `handoff.js` then, identically on every device:

1. Downloads `intake.json` (Blob + object URL) from the validated object.
2. Shows a success screen with an **Email it in** button that opens a
   prefilled `mailto:` — recipient = the return address; subject composed
   from `runner.name` + `goal.race` (e.g. "RunDrafter intake — Alex Smith,
   Melbourne Marathon"); body a basic message asking the runner to attach
   the `intake.json` they just downloaded.
3. Also shows the return address as plain text and a **Download again**
   link, so the flow is recoverable if the download or mail app misbehaves.

Ajv errors and cross-field errors render inline against their fields;
warnings render in a separate, non-blocking notice.

---

## Testing

Runtime is zero-toolchain and so is the test toolchain: **no node or npm,
anywhere** (see ADR 001). Tests run under `pytest`, driving a real browser
via Playwright's Python bindings (`pip`-installed dev dependency; `playwright
install` fetches browser binaries directly, no npm involved). A test loads
`index.html` from disk, sets form state (either through the DOM or by
calling `assemble.js` in-page via Playwright's `page.evaluate`), and asserts
on the result — so the *same* `assemble.js` + vendored Ajv + schema the
browser ships is what's under test, not a second runtime's copy of it.
`handoff.js`'s download/mailto is covered the same way (Playwright can
intercept downloads and `mailto:` navigation).

- **Assembler tests** (`tests/test_assemble.py`): feed form-state fixtures
  into `assemble.js` in-page, assert the assembled object validates against
  the vendored schema (via Python's `jsonschema`, already a dependency), and
  assert each cross-field rule fires (pruning, disclaimer gate, date
  ordering + event-window + duplicate-date + schedule override rules,
  anchor-session pairing) and each warning fires (stale recent result).
- **Golden reproduction:** a fixture reproduces `schema/intake-example.json`'s
  structure from a plausible form-state, proving the form can emit the
  reference shape.
- **Contract drift check** (CI): committed `schema/*` matches a fresh sync.
- **DOM smoke test:** fill the real form fields → download → validate,
  folded into the same Playwright suite rather than deferred as a separate
  optional tier, since the browser-driven approach is now the only test
  tier there is.
- **Stage-1 parity** (`tests/test_stage1_parity.py`, local only): pipes the
  fixtures' assembled intakes and the DOM smoke test's downloaded intake
  through the sibling checkout's real `rundrafter validate` CLI, so a
  cross-field rule this suite considers passing is checked against
  upstream's actual implementation, not just this repo's re-implementation
  of it. Skipped without a `../rundrafter` checkout.

Run the narrowest relevant test while iterating; widen to the full file
before done.
