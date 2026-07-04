# CLAUDE.md — rundrafter-webform

@.fieldkit/CLAUDE.md
@.fieldkit/conventions/python/README.md

## Project guide

See `README.md` for the overview and the intake contract this form
implements, and `docs/spec/webform.md` for the build spec — the decisions,
architecture, and the ordered T0–T9 build plan. Its progress checklist is the
source of truth for what's built; tick it in the commit that does the work.

## Cross-field validation parity

`assets/assemble.js`'s cross-field rules mirror upstream `run-drafter`'s
`src/rundrafter/validate.py` stage-1 checks (see
`docs/spec/pre-deploy-hardening.md`, finding A and plan H5 — this drifted
silently once already). Before changing that validation, or after any
contract sync (`just sync-contract`), diff `assemble.js` against the sibling
checkout's `validate.py` + `docs/spec/contracts.md`, run
`tests/test_stage1_parity.py`, and if the rules changed, re-pin with
`uv run python scripts/sync_contract.py --update-rules-revision`.
