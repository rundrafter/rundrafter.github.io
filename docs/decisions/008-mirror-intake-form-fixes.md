# 008 - Mirror the intake form fixes (current fitness optional; long run in the weekly template)

## Decision

Mirror upstream `rundrafter`'s ADRs 018 (current fitness becomes optional,
with a beginner starting-volume default filling the gap) and 019 (the long
run is pinned via a `type: "long"` weekly session template entry;
`weekly_schedule.long_run_day` is removed as a separate override): drop the
`required` attribute from the two current-fitness inputs once ADR 018's
contract lands, and remove the dedicated "Long run day" `<select>` once ADR
019's contract lands, in favour of adding a "Long run" entry to the weekly
session template.

## Reason

This repo has no separate stance to litigate, same as ADR 007. Once the
vendored contract is re-synced, `schema/intake-schema.json` will make
`current_fitness` optional and will reject `weekly_schedule.long_run_day`
outright (`additionalProperties: false`), so a form that still required the
former or still offered the latter would either turn away a beginner the
contract now welcomes, or submit a field the pipeline no longer accepts.

Unlike ADR 007, the two upstream ADRs here land as **separate** build-plan
stages (018 in Stage 3, 019 in Stage 4 of
`build-plan-intake-form-fixes.md`), not one bundled rework, so this ADR
covers both decisions but its consequences are applied in two independent
passes - one per upstream stage landing - each with its own contract
re-sync, not a single combined one.

## Consequences

- `schema/intake-schema.json`, `schema/intake-example.json`, and
  `assets/schema.js` are re-vendored via `just sync-contract` twice, once
  after each upstream stage lands (018, then 019 - or in whichever order
  they land upstream).
- `index.html`: the `required` attribute is dropped from
  `fitness-weekly-distance` and `fitness-longest-run`, with copy noting a
  runner new to running can leave both blank (ADR 018); the "Long run day"
  `<select>` is removed, and the weekly-session-template help text explains
  that a "Long run" entry there pins the day (ADR 019).
- `assets/assemble.js`: no change needed for ADR 018 (`omitEmpty` already
  drops the two fields when left blank). For ADR 019, `pruneWeeklySchedule`
  drops its `long_run_day` handling, and `validateCrossField`'s
  unavailable-day check re-keys from the removed field to a `type: "long"`
  `preferred_sessions` entry; a new client-side check rejects a second
  `long` entry, mirroring upstream `validate.py`.
- `docs/architecture.md`'s field-inventory table and "Rules the schema
  can't express" section are updated to match, for each change as it lands.
- `tests/fixtures/golden.json` / `valid.json` and the relevant test files
  are updated, including a beginner (no `current_fitness`) form-state
  fixture and a "long run pinned via the template" fixture.
- `rules_revision` in `schema/SOURCE.md` is re-pinned after each sync, per
  the parity workflow in `CLAUDE.md`.

Status: Proposed - flips to Accepted once both upstream ADRs (018, 019) are
Accepted and this repo's corresponding stages (018's mirrored webform step,
019's mirrored webform step) are complete, mirroring the build plan's own
0.2.
