# rundrafter-webform

The runner-facing intake form for [RunDrafter](https://github.com/rundrafter/rundrafter) -
a static, client-side page that collects a runner's details and assembles
them into an `intake.json` for download. No backend: the runner emails the
file back, and it's fed into the RunDrafter pipeline manually.

Live at <https://rundrafter.github.io/>. This is phase 2 of RunDrafter's
delivery plan; for the architecture, design rationale, and how this form fits
the wider pipeline, see the main
[`rundrafter`](https://github.com/rundrafter/rundrafter) repo's
[`docs/webform-architecture.md`](https://github.com/rundrafter/rundrafter/blob/main/docs/webform-architecture.md)
and ADRs 025-032 in
[`docs/decisions/`](https://github.com/rundrafter/rundrafter/tree/main/docs/decisions) -
this repo intentionally keeps very little documentation of its own, since
it's public and a runner filling in the form has no reason to see it.

## Contract

This project depends on `rundrafter` only through the stable **intake
contract**:

- [`docs/intake.md`](https://github.com/rundrafter/rundrafter/blob/main/docs/intake.md) -
  field-by-field reference for the form.
- [`docs/intake-schema.json`](https://github.com/rundrafter/rundrafter/blob/main/docs/intake-schema.json) -
  the authoritative schema the output must validate against.
- [`docs/intake-example.json`](https://github.com/rundrafter/rundrafter/blob/main/docs/intake-example.json) -
  a golden fixture example.

Keep this form in sync with those documents rather than duplicating the
contract here.

## Local development

No node or npm anywhere in this repo — all tooling is Python, via
[`uv`](https://docs.astral.sh/uv/) and [`just`](https://just.systems/). See
[ADR 025](https://github.com/rundrafter/rundrafter/blob/main/docs/decisions/025-webform-vanilla-no-build-step.md)
for why.

```sh
just serve            # serve the form at http://localhost:8000
just test             # run the test suite (pytest + Playwright)
just lint             # markdown lint
just check            # lint + test
```

The page needs a static server rather than `file://` — Chrome refuses
module-script fetches for `file://` documents, so `just serve` (or GitHub
Pages, in production) is required even for local use.

### Syncing the intake contract

The form depends on the sibling `rundrafter` repo only through the intake
contract (schema + example + field reference). `scripts/sync_contract.py` is
the only thing that writes `schema/*` and `assets/schema.js`:

```sh
just sync-contract     # vendor schema + example from ../rundrafter, regen schema.js
just check-contract    # check for drift against upstream, without writing
```

See [`docs/contract-sync.md`](docs/contract-sync.md) for the sync mechanics,
the pinned-revision/`rules_revision` bookkeeping, and the cross-field parity
workflow.

## Status

The form collects the full intake, validates client-side against the
vendored schema, and hands off via download + prefilled email, with branch
protection on `main`.

Privacy note: intakes carry fitness details and arrive by ordinary email -
delete each `intake.json` from the inbox once it's been fed into the
pipeline.
