# rundrafter-webform

The runner-facing intake form for [RunDrafter](https://github.com/rundrafter/rundrafter) -
a static, client-side page that collects a runner's details and assembles
them into an `intake.json` for download. No backend: the runner emails the
file back, and it's fed into the RunDrafter pipeline manually.

This is phase 2 of RunDrafter's delivery plan - see
[`docs/spec/structure-and-phasing.md`](https://github.com/rundrafter/rundrafter/blob/main/docs/spec/structure-and-phasing.md)
in the main repo for the full roadmap and rationale.

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

The form depends on the sibling `rundrafter` repo only through the intake
contract (schema + example + field reference). `scripts/sync_contract.py` is
the only thing that writes `schema/*` and `assets/schema.js`:

```sh
just sync-contract     # vendor schema + example from ../rundrafter, regen schema.js
just check-contract    # check for drift against upstream, without writing
```

Locally this reads from a sibling `../rundrafter` checkout. The pinned
upstream revision is recorded in [`schema/SOURCE.md`](schema/SOURCE.md).
There's no automated CI drift check yet — `rundrafter` is private, so an
unauthenticated fetch in CI would 404 (tracked in
[#29](https://github.com/rundrafter/rundrafter.github.io/issues/29)). Run
`just check-contract` by hand before relying on the vendored copy being
current.

## Status

Live at <https://rundrafter.github.io/>: the form collects the full intake,
validates client-side against the vendored schema, and hands off via
download + prefilled email, with branch protection on `main`. See
[`docs/architecture.md`](docs/architecture.md) for how it's built and
[`docs/decisions/`](docs/decisions/) for the design rationale.

Privacy note: intakes carry fitness details and arrive by ordinary email (see
[ADR 003](docs/decisions/003-uniform-mailto-handoff.md)) — delete each
`intake.json` from the inbox once it's been fed into the pipeline.
