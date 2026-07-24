# Contract sync mechanism

How this form stays in sync with the `rundrafter` intake contract. For *why*
the form validates against the real schema client-side at all, see ADR 026
in the `rundrafter` repo's `docs/decisions/`; this doc covers only the
mechanics of keeping the vendored copy current.

`scripts/sync_contract.py` is the **only** thing that writes `schema/*` and
`assets/schema.js` - so drift is always a one-command fix, never a hand
edit:

```sh
just sync-contract     # vendor schema + example from ../rundrafter, regen schema.js
just check-contract    # check for drift against upstream, without writing
```

1. Copy `intake-schema.json` and `intake-example.json` from the upstream
   source - locally from the sibling checkout (`../rundrafter/docs/`), or
   in CI from GitHub raw at the pinned revision in `schema/SOURCE.md`.
2. Regenerate `assets/schema.js` by wrapping the JSON as
   `export default <json>;`. Inlining as a module means the page needs no
   `fetch`, so validation works from `file://` too.
3. Record the upstream commit SHA in `schema/SOURCE.md`.

Locally this reads from a sibling `../rundrafter` checkout. There's no
automated CI drift check yet - `rundrafter` is private, so an
unauthenticated fetch in CI would 404 (tracked in
[#29](https://github.com/rundrafter/rundrafter.github.io/issues/29)). Run
`just check-contract` by hand before relying on the vendored copy being
current.

## Cross-field rule parity

`assets/assemble.js`'s cross-field rules (date ordering, event windows,
schedule checks - see `rundrafter`'s `docs/webform-architecture.md` for the
full list) mirror upstream `rundrafter`'s `src/rundrafter/validate.py`
stage-1 checks rule-for-rule, so an intake this form accepts never bounces
back from the pipeline.

`schema/SOURCE.md` pins a separate `rules_revision`: the upstream hash of
`validate.py` + `docs/spec/contracts.md` at the last cross-field parity
review. These aren't vendored files, so `just check-contract` only compares
hashes - against the sibling checkout, locally; it's a no-op without one -
and reports "rules changed upstream since last parity sync" rather than
diffing content.

Before changing any cross-field rule, or after any contract sync, diff
`assemble.js` against the sibling `rundrafter` checkout's `validate.py` +
`docs/spec/contracts.md`, run `tests/test_stage1_parity.py`, and if the
rules changed, re-pin with:

```sh
uv run python scripts/sync_contract.py --update-rules-revision
```

`tests/test_stage1_parity.py` is the executable half of the same guard: it
pipes every intake this suite considers valid through the sibling's real
`rundrafter validate` CLI (skipped without a `../rundrafter` checkout).

This validation drifted silently from upstream once already (pre-deploy
audit, 2026); the parity test and the `rules_revision` hash pin exist to
catch it happening again.
