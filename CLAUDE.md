# CLAUDE.md — rundrafter-webform

@.fieldkit/CLAUDE.md
@.fieldkit/conventions/python/README.md

## Project guide

See `README.md` for the overview and setup, and `docs/contract-sync.md` for
the local mechanics of keeping the vendored schema and cross-field rules in
sync with `rundrafter`. This repo keeps very little documentation of its
own beyond that, since it's public: the intake contract, field reference,
validation-rule inventory, file layout, and design rationale (ADRs 025-032)
live in the sibling `rundrafter` repo's `docs/webform-architecture.md` and
`docs/decisions/` — read those for anything beyond local dev/sync
mechanics.

## Cross-field validation parity

`assets/assemble.js`'s cross-field rules mirror upstream `rundrafter`'s
`src/rundrafter/validate.py` stage-1 checks (see that repo's
`docs/webform-architecture.md`'s "Rules the schema can't express" — this
drifted silently once already). Before changing that validation, or after
any contract sync (`just sync-contract`), diff `assemble.js` against the
sibling checkout's `validate.py` + `docs/spec/contracts.md`, run
`tests/test_stage1_parity.py`, and if the rules changed, re-pin with
`uv run python scripts/sync_contract.py --update-rules-revision` (see
`docs/contract-sync.md`).
