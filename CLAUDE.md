# CLAUDE.md — rundrafter-webform

@.fieldkit/CLAUDE.md
@.fieldkit/conventions/python/README.md

## Project guide

See `README.md` for the overview and setup, and `docs/architecture.md` for
the intake contract, field reference, validation rules, and file layout —
the living reference for how the form is built. Decisions and their
rationale live in `docs/decisions/`.

## Cross-field validation parity

`assets/assemble.js`'s cross-field rules mirror upstream `run-drafter`'s
`src/rundrafter/validate.py` stage-1 checks (see `docs/architecture.md`'s
"Rules the schema can't express" — this drifted silently once already).
Before changing that validation, or after any contract sync
(`just sync-contract`), diff `assemble.js` against the sibling checkout's
`validate.py` + `docs/spec/contracts.md`, run `tests/test_stage1_parity.py`,
and if the rules changed, re-pin with
`uv run python scripts/sync_contract.py --update-rules-revision`.
