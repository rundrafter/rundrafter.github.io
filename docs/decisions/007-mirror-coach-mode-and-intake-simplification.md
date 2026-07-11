# 007 - Mirror coach mode and the intake simplification

## Decision

Rebuild the recurring-sessions UI as a **weekly session template** (broad
session type, min/max distance, a skip-tailoring tickbox), make the Recent
Result section optional, add a proper goal-time selector (specific time /
just finish / suggest a time), and drop the age input, the disclaimer
checkbox, the `rest_days` multi-select, the strength & cross-training
section, the `warmup_jog` checkbox, and the preferences radio - relabelling
Name to **Plan Title** (optional) and folding other events into the
Restrictions section as a dated template-style row.

## Reason

This mirrors upstream `rundrafter`'s own change - see its ADRs 014
(broad session types and per-session skip-tailoring, "coach mode"), 015
(support runners with no recent result via conservative default paces), 016
(RunDrafter-suggested goal time), and 017 (remove the intake
disclaimer/consent gate, plus the related field removals it bundles: `age`,
the `rest_days` override, `warmup_jog`, `strength_cross`, `preferences`, and
the `other_events` restructure) for the full reasoning. This repo has no
separate stance to litigate: once the vendored contract is re-synced,
`schema/intake-schema.json` requires the new weekly-template shape and
rejects `effort`, `consent`, `strength_cross`, `preferences`, `age`, and the
old `rest_days`/`other_events` shapes outright (`additionalProperties:
false`), so a form that kept the old fields would produce intakes the
pipeline bounces, and a form that didn't offer the new ones couldn't express
coach mode or a beginner/suggested-goal intake at all.

The four upstream ADRs land as one bundled intake rework (per upstream's
`docs/spec/build-plan-generic-coach-mode.md`), so this repo tracks them with
one mirrored ADR rather than four - the webform-side consequence is a single
coordinated pass over the same files either way.

## Consequences

- `schema/intake-schema.json`, `schema/intake-example.json`, and
  `assets/schema.js` are re-vendored via `just sync-contract` rather than
  hand-edited (see `schema/SOURCE.md`); this also reconciles the
  already-stale `b_races[].target_time` requirement noted in upstream's
  research.
- `index.html`: Name relabelled to **Plan Title** (optional, example
  placeholders); the age input, the disclaimer/consent checkbox, the
  `rest_days` multi-select, the strength & cross-training section, and the
  `warmup_jog` checkbox are removed; the recurring-sessions repeating group
  is rebuilt as the weekly template (broad-type `<select>`, description,
  min/max distance, and a skip-tailoring tickbox shown for
  Quality/Strength/Long/Cross-training); the goal block gains a proper time
  selector plus *specific time / just finish / suggest a time* radios; other
  events move into Restrictions as a dated template-style row; the
  preferences radio is removed.
- `assets/assemble.js` / `assets/form.js`: `gatherFormState`, the pruning
  helpers, and `validateCrossField`/`validateWarnings` are updated for the
  new shapes; the disclaimer gate and the rest-day/effort parity rules are
  dropped; `distance_max: 0` range handling is added; `recent_result`
  becomes optional; the suggest-a-time radio emits `target_time: "suggest"`.
- `docs/architecture.md`'s field-inventory table and "Rules the schema can't
  express" section are updated to match.
- `tests/fixtures/golden.json` / `valid.json` and `test_assemble.py`,
  `test_stage1_parity.py`, `test_contract.py`, `test_handoff.py` are updated,
  with new coach-mode and beginner form-state fixtures.
- `rules_revision` in `schema/SOURCE.md` is re-pinned to the upstream commit
  that lands the stage-2 engine changes (`validate.py`/`resolve.py`/
  `calibrate.py`/`schedule.py`), per the parity workflow in `CLAUDE.md`.

Status: Accepted.
