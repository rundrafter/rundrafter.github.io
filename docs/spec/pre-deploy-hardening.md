# Pre-deploy hardening — review findings and plan

A pre-deploy (T9) code review of the finished T0–T8 build, comparing the
shipped form against the *actual* upstream pipeline — `run-drafter`'s
`src/rundrafter/validate.py` and `docs/spec/contracts.md` — not just the
vendored JSON schema. The findings below are the review record; the plan at
the foot is the ordered fix list, one PR per step, ticked in the commit that
does the work. **T9 is gated on this plan completing.**

Decision (owner-approved): the form gets a non-blocking **warnings channel**
alongside the blocking-rule fixes — `assemble()` returns
`{ intake, errors, warnings }`.

---

## Findings

### A. Contract-parity gaps (form accepts what stage 1 rejects) — highest priority

The product flow is "runner emails intake.json, operator feeds it in
manually", so any intake the form accepts but stage 1 rejects means chasing
the runner by email after they believe they're done. Upstream `validate.py`
blocks on all of these; the form checks none (or a weaker version):

1. **`start_date` strictly `<` `goal.date`** (`DATE_ORDER_START_AFTER_GOAL`).
   The form allows equality — `webform.md` said `≤` (spec drift) and
   `tests/test_assemble.py::test_start_date_equal_to_goal_date_passes`
   asserts the wrong behaviour.
2. **`recent_result.date` `≤ start_date`** (`DATE_ORDER_RESULT_AFTER_START`).
   Unchecked — a future-dated result passes.
3. **b_races / other_events dates strictly between `start_date` and
   `goal.date`** (`DATE_OUT_OF_WINDOW`). Form only checks `< goal.date`.
4. **No two events (across b_races + other_events) share a date**
   (`DUPLICATE_EVENT_DATE`). Unchecked.
5. **`long_run_day` not in `rest_days`** (`LONG_RUN_DAY_IS_REST`). Unchecked.
6. **`days_available ≥ 3`** (`DAYS_AVAILABLE_TOO_FEW`). Form allows 1–7
   (HTML `min="1"`).
7. **Preferred-session days not on rest days**
   (`PREFERRED_SESSION_ON_REST_DAY`). Unchecked.

Upstream also *warns* (non-blocking) when `recent_result.date` is >183 days
before `start_date` (`RECENT_RESULT_OLD`); `webform.md` separately promised
advisory strength/rest/days-available consistency warnings that were never
implemented. Both belong in the new warnings channel.

Root cause of the drift: `webform.md`'s "Source of truth" listed only
`intake-schema.json` / `intake-example.json` / `intake.md`, but the
cross-field rules actually live in `run-drafter/docs/spec/contracts.md` +
`validate.py`. The spec's rules section was hand-derived and went stale.

### B. Bugs

8. **mailto `+`-encoding** (`assets/handoff.js`, `buildMailtoUrl`):
   `URLSearchParams.toString()` form-encodes spaces as `+`, but RFC 6068
   mailto URLs need percent-encoding — most mail clients show
   `RunDrafter+intake+—+Alex+Smith` literally. The test masks this:
   `tests/test_handoff.py::parse_mailto` uses `parse_qs`, which decodes `+`
   as space just like `URLSearchParams`. Fix with `encodeURIComponent`;
   tighten the test to `unquote` only and assert no raw `+` in the query.
9. **`health_screen.other_reason` missing from the form** (`intake.md`
   lists it; `webform.md`'s own table lists it). `assemble.js` already
   excludes it from the health-flag gate (correct — upstream gates only on
   the 8 booleans), so only the `index.html` input is missing;
   `gatherFormState`/`omitEmpty` handle the rest.

### C. Error-surfacing UX (novalidate + raw Ajv messages)

The form uses `novalidate`, so empty required fields flow through to Ajv and
come back as `"goal: /goal must have required property 'race'"` — and
because the error path is the *section* (`goal`), not the field,
`markFieldError` finds no `[name="goal"]` element and the message lands
summary-only, not inline.

10. Map Ajv `required`/`dependentRequired` errors to the missing field:
    `path + "." + err.params.missingProperty` in `form.js`, with a friendly
    message. Also fixes repeating-row errors (`injuries.0.area` etc.).
11. `rest_days` unchecked → `omitEmpty` drops the key → cryptic schema
    error. Add a friendly cross-field error ("Select at least one rest
    day."), and likewise for `days_available < 3` (finding 6).
12. Anchor-session `dependentRequired` (distance without effort or vice
    versa) → cryptic row-level Ajv error. Add a friendly cross-field
    message naming the row.

### D. Minor cleanups

13. `consent.health_acknowledged: false` is emitted on every real
    submission (single checkbox → boolean kept by `omitEmpty`) even when no
    health flag is raised and the control is hidden. Omit it when `false`.
14. `tests/test_handoff.py::test_return_email_constant` reads
    `Path("assets/handoff.js")` relative to CWD; make it repo-root-relative
    like the other tests.
15. CI runs only on `pull_request` — add a `push: branches: [main]` trigger
    so main gets a post-merge run.
16. Deploy prep: add `.nojekyll`; optional favicon +
    `<meta name="description">`.

### E. Security audit (2026-07-04)

A pre-deploy security audit of the whole static site (not just the diff)
found **no vulnerabilities that block deploy**. Verified sound: all
user-controlled values reach the DOM via `textContent` (no `innerHTML`
with user data); `buildMailtoUrl` encodes header-injection characters;
`assets/ajv.bundle.js` hash matches both `AJV_SOURCE.md` and cdnjs's
published SRI for `ajv/8.17.1/ajv2020.min.js`; no secrets in the tree
(relevant because Pages serves every committed file); no external
requests at runtime — the site is fully self-contained.

Hardening actions, folded into H4:

17. **Meta CSP.** Pages can't set response headers, but a
    `<meta http-equiv="Content-Security-Policy">` tag covers most
    directives, and the site's self-contained design makes a strict
    policy free: `default-src 'none'; script-src 'self' 'unsafe-eval';
    style-src 'self'; img-src 'self'; form-action 'none'; base-uri
    'none'`. `'unsafe-eval'` is required, not optional — the DOM smoke
    test caught this: Ajv compiles the schema into a validator via
    `new Function` at runtime (`form.js`'s `ajv.compile`), which CSP
    treats as eval, and ADR 001's no-build-step rule means there's no
    way to ship a precompiled eval-free validator instead.
    (`frame-ancestors` doesn't work via meta; acceptable — the page has
    no authenticated or destructive actions to clickjack.)
18. **CI supply-chain pinning** (`.github/workflows/ci.yml`). The just
    installer is `curl | bash` from just.systems on every run — replace
    with a SHA-pinned `extractions/setup-just` (or checksum-verify the
    script). SHA-pin `actions/checkout` too, matching how `setup-uv` is
    already pinned.

Noted for the human-only T9 steps, not the build:

- **Branch protection before Pages goes live.** ADR 004 makes
  push-to-main the deploy mechanism, so main becomes production at
  transfer time: require PRs on main, keep the org push/admin set
  minimal.
- **Privacy sign-off.** The intake includes health-screen data and the
  handoff is ordinary email to a personal inbox (ADR 003) — defensible
  for a manual pilot, but add a sentence on the page telling runners the
  file travels by ordinary email, and delete intakes after processing.

### Explicitly fine / no action

- Repo hygiene clean (caches and local settings correctly ignored).
- `consent.terms_accepted` intentionally absent (optional until a paid ToS
  exists).
- `other_reason` correctly does *not* trigger the acknowledgement gate
  (matches upstream).
- `b_races` ≤3 enforced in UI; upstream schema has no `maxItems` (upstream's
  gap — belongs in `run-drafter`).
- XSS-safe (errors via `textContent`); Ajv bundle pinned with SRI notes.
- Styling/a11y solid (theme-aware tokens, focus rings,
  `aria-invalid`/`aria-describedby`, error summary `role="alert"`).

---

## Plan

Spec-driven order: fix the spec first, then make code match it, one
reviewable PR per step (fieldkit git conventions apply: branch prefixes,
Conventional Commits, approval before opening each PR).

### H1 — spec: sync cross-field rules with the upstream contract

Branch `chore/spec-contract-parity`; `docs/` only.

- Add `run-drafter/docs/spec/contracts.md` (constraints column) +
  `validate.py` to `webform.md`'s "Source of truth" as the authority for
  cross-field rules.
- Rewrite "Rules the schema can't express" to mirror stage 1 exactly: the
  seven blocking rules above (fixing `≤` → `<`), plus a **Warnings**
  subsection (stale recent result; strength/rest/days-available
  consistency) and the `{ intake, errors, warnings }` assemble contract.

*DoD:* `webform.md`'s rules section matches `validate.py` rule-for-rule.

### H2 — feat: validation parity + warnings channel

Branch `feature/stage1-validation-parity`. Files: `assets/assemble.js`,
`assets/form.js`, `assets/styles.css`, `index.html`,
`tests/test_assemble.py`, `tests/fixtures/*`.

- `validateCrossField`: add the seven blocking rules (mirror upstream
  semantics). New `validateWarnings`; `assemble` returns
  `{ intake, errors, warnings }`.
- `form.js`: render warnings as a non-blocking notice (`#form-warnings`,
  styled like `#form-errors` but muted/amber; shown without blocking the
  download). `styles.css`: warning tokens, light + dark.
- `index.html`: `days_available` `min="3"`.
- Tests: block + pass cases per rule (boundary dates); warnings assertions;
  **flip** `test_start_date_equal_to_goal_date_passes` to assert equality
  blocks. `valid.json` and `golden.json` already satisfy the stricter rules
  (verified during review) — no fixture changes expected.

*DoD:* each stage-1 blocking rule has a failing-input test that blocks and a
passing-input test that validates; warnings surface without blocking.

Scope note: only `RECENT_RESULT_OLD` shipped as a warning. The other
promised warning — "`strength_days` / `rest_days` / `days_available` should
be consistent" — has no formula anywhere upstream or in `intake.md` beyond
that one adjective, so implementing it now would mean inventing product
behavior rather than mirroring a spec. Deferred; needs its own product
decision before a follow-up implements it.

### H3 — fix: mailto encoding, other_reason field, inline error mapping

Branch `bugfix/handoff-and-error-surfacing`. Files: `assets/handoff.js`,
`assets/form.js`, `assets/assemble.js`, `index.html`,
`tests/test_handoff.py`, `tests/test_assemble.py`.

- `buildMailtoUrl`: percent-encode via `encodeURIComponent` (drop
  `URLSearchParams`); test parses with `unquote` only and asserts no bare
  `+` in the URL.
- `index.html`: add `health_screen.other_reason` text input (optional; label
  per `intake.md`).
- `form.js`: Ajv `required`/`dependentRequired` → field-level path via
  `params.missingProperty`, friendly message, raw fallback otherwise.
- `assemble.js`: friendly errors for rest-days and anchor-session pairing;
  omit `consent.health_acknowledged` when `false`.
- Fix `test_return_email_constant` path (finding 14).

*DoD:* an empty required field shows an inline `.field-error` next to the
input; mailto href contains no `+`; `other_reason` round-trips (blank →
omitted).

### H4 — chore: deploy prep

Branch `chore/deploy-prep`. Add `.nojekyll`; `push: branches: [main]` CI
trigger; favicon + meta description; the security-audit hardening
(finding 17: meta CSP in `index.html`; finding 18: pin the just installer
and SHA-pin `actions/checkout` in `ci.yml`); the audit's privacy sentence
on the success screen ("this file travels by ordinary email"); refresh
README "Status" and tick this plan's checklist. T9 then proceeds via the
human-only manual steps in `webform.md` — which now also include branch
protection on main and the intake-deletion practice (section E).

*DoD:* `just check` green with the CSP in place (the DOM smoke test
exercises the page under the policy); CI green with pinned actions;
README/spec reflect reality; repo ready for the Pages transfer.

### H5 — feat: contract-drift prevention

Guards against the root cause recurring: upstream rule changes landing
silently. Branch `feature/drift-prevention`. Files: `tests/` (new parity
test), `scripts/sync_contract.py`, `schema/SOURCE.md`, `CLAUDE.md`.

- **Executable parity test.** Upstream ships a validate CLI
  (`rundrafter validate <intake> --canonical … --report …`, exit 1 on
  errors with printed codes). New pytest: pipe every intake this suite
  considers valid — the fixtures plus the DOM smoke test's downloaded
  file — through `uv run --project ../run-drafter rundrafter validate`
  and assert zero errors. `pytest.mark.skipif` when `../run-drafter` is
  absent (CI can't run it until the PAT from `webform.md` manual step 8
  exists).
- **Widen the drift tripwire.** `sync_contract.py` pins only
  schema + example — exactly why the rules drifted invisibly. Also record
  in `SOURCE.md` the upstream git hash of `docs/spec/contracts.md` and
  `src/rundrafter/validate.py` at the last parity review;
  `just check-contract` compares and reports "rules changed upstream since
  last parity sync". Hash-pin, don't vendor: this repo becomes a public
  Pages site and those files are a private repo's internals.
- **Standing instruction for agents.** Webform `CLAUDE.md`: cross-field
  validation mirrors run-drafter stage 1 — before changing `assemble.js`
  validation or after any contract sync, diff against upstream
  `validate.py` and run the parity test.
- **Reciprocal upstream tripwire** (separate small PR in `run-drafter`):
  note on `validate.py`'s intake-rule section and/or its CLAUDE.md that
  `rundrafter-webform` mirrors these rules client-side, so changing them
  requires a parity sync there. Drift originates upstream; the reminder
  must live where the change happens.

*DoD:* parity test green against the sibling checkout and red if a stage-1
rule is deliberately broken locally; `just check-contract` flags a rule-file
change upstream; both repos carry the cross-repo instruction.

---

## Verification

- Per PR: `just check` (lint + full pytest/Playwright suite) green.
- End-to-end after H3: `just serve`, then (a) compliant intake → download
  succeeds, mailto href shows percent-encoded spaces; (b) an intake
  violating each new rule → inline + summary errors, no download; (c) stale
  recent result → warning shown, download still proceeds.
- Parity proof: run run-drafter's stage-1 validate (sibling checkout) on a
  downloaded `intake.json` — it must pass with no errors.

## Out of scope

- CI contract-drift job (needs a PAT for the private upstream —
  `webform.md` manual step 8).
- Upstream schema gaps (e.g. `b_races` missing `maxItems: 3`) — file
  against `run-drafter`.

## Progress

- [x] H1 — Spec sync (cross-field rules ← upstream contract)
- [x] H2 — Validation parity + warnings channel
- [x] H3 — mailto encoding, other_reason, inline error mapping
- [x] H4 — Deploy prep (incl. security-audit hardening: CSP, CI pinning)
- [x] H5 — Contract-drift prevention (parity test, widened tripwire,
  cross-repo instructions, incl. `run-drafter`'s reciprocal tripwire
  comment, merged upstream in #60)
