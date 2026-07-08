# 005 - Remove the health-screen step and its consent gate

## Decision

Drop the health-screen questions (the `health_screen` section - 8 PAR-Q
boolean checkboxes plus `other_reason`) and their `consent.health_acknowledged`
gate from the form, `assemble.js`, and the vendored contract. The form now
collects only `consent.disclaimer_accepted`; the medical-guidance disclaimer
stays, unchanged.

## Reason

This mirrors upstream `rundrafter`'s own removal - see its ADR 008 for the
full reasoning (sensitive health PII collected for no clinically acted-upon
benefit; a self-answered checkbox doesn't meaningfully offset the risk the
disclaimer already covers). This repo has no separate stance to litigate:
`schema/intake-schema.json` now rejects `health_screen` outright
(`additionalProperties: false`), so a form that kept asking for it would
produce intakes the pipeline bounces.

## Consequences

- `schema/intake-schema.json`, `schema/intake-example.json`, and
  `assets/schema.js` were re-vendored via `just sync-contract` rather than
  hand-edited (see `schema/SOURCE.md`).
- `index.html` drops the health-screen section and the conditional
  acknowledgement block inside Consent; `assets/form.js` drops
  `setupHealthAcknowledgement`; `assets/assemble.js` drops the health-flag
  cross-field rule and the `health_screen` key from the assembled intake.
- `docs/architecture.md`'s field table and "Rules the schema can't express"
  section, and `tests/test_assemble.py`'s health-screen/acknowledgement
  tests and fixtures, are updated to match.
- `rules_revision` in `schema/SOURCE.md` is re-pinned to the upstream commit
  that removed the health-gate rule from `validate.py`, per the parity
  workflow in `CLAUDE.md`.

Status: Accepted.
