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

## Local development

No node or npm anywhere in this repo — all tooling is Python, via
[`uv`](https://docs.astral.sh/uv/) and [`just`](https://just.systems/). See
[ADR 001](docs/decisions/001-vanilla-no-build-step.md) for why.

```sh
just serve            # serve the form at http://localhost:8000
just test             # run the test suite (pytest + Playwright)
just lint             # markdown lint
just check            # lint + test
```

The page needs a static server rather than `file://` — Chrome refuses
module-script fetches for `file://` documents, so `just serve` (or GitHub
Pages once deployed) is required even for local use.

### Syncing the intake contract

The form depends on the sibling `run-drafter` repo only through the intake
contract (schema + example + field reference). `scripts/sync_contract.py` is
the only thing that writes `schema/*` and `assets/schema.js`:

```sh
just sync-contract     # vendor schema + example from ../run-drafter, regen schema.js
just check-contract    # check for drift against upstream, without writing
```

Locally this reads from a sibling `../run-drafter` checkout. The pinned
upstream revision is recorded in [`schema/SOURCE.md`](schema/SOURCE.md).
There's no automated CI drift check yet — `run-drafter` is private, so an
unauthenticated fetch in CI would 404 (see `docs/spec/webform.md`'s manual
steps for closing that gap). Run `just check-contract` by hand before relying
on the vendored copy being current.

## Status

Core build (T0–T8) is done: the form collects the full intake, validates
client-side against the vendored schema, and hands off via download +
prefilled email. Before deployment (T9), a pre-deploy review found fixes the
form needs — chiefly cross-field validation parity with the upstream
pipeline — planned in
[`docs/spec/pre-deploy-hardening.md`](docs/spec/pre-deploy-hardening.md).
The build plan, decisions, and progress checklist live in
[`docs/spec/webform.md`](docs/spec/webform.md); design rationale is in
[`docs/decisions/`](docs/decisions/).
