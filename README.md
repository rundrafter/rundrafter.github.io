# run-drafter-webform

The runner-facing intake form for [RunDrafter](https://github.com/eirkkr/run-drafter) -
a static, client-side page that collects a runner's details and assembles
them into an `intake.json` for download. No backend: the runner emails the
file back, and it's fed into the RunDrafter pipeline manually.

This is phase 2 of RunDrafter's delivery plan - see
[`docs/spec/structure-and-phasing.md`](https://github.com/eirkkr/run-drafter/blob/main/docs/spec/structure-and-phasing.md)
in the main repo for the full roadmap and rationale.

## Contract

This project depends on `run-drafter` only through the stable **intake
contract**:

- [`docs/intake.md`](https://github.com/eirkkr/run-drafter/blob/main/docs/intake.md) -
  field-by-field reference for the form.
- [`docs/intake-schema.json`](https://github.com/eirkkr/run-drafter/blob/main/docs/intake-schema.json) -
  the authoritative schema the output must validate against.
- [`docs/intake-example.json`](https://github.com/eirkkr/run-drafter/blob/main/docs/intake-example.json) -
  a golden fixture example.

Keep this form in sync with those documents rather than duplicating the
contract here.

## Status

Spec written, implementation not started. The build plan, decisions, and
progress checklist live in [`docs/spec/webform.md`](docs/spec/webform.md).
