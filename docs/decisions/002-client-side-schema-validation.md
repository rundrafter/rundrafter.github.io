# 002 - Validate against the real schema, client-side, before handoff

## Decision

Before the form hands off an `intake.json`, it validates the assembled object
against the authoritative JSON Schema in the browser. A vendored copy of
`intake-schema.json` is compiled by [Ajv](https://ajv.js.org/) (committed as a
pinned standalone browser bundle) and run at submit time; an object that fails
validation shows errors inline and blocks the download.

The schema is vendored, never forked: `scripts/sync_contract.py` copies it from
`run-drafter` (see the spec's "Contract sync mechanism").

## Reason

The form's entire reason to exist is to let a non-developer produce a *valid*
intake instead of hand-authoring JSON. Checking the output against the real
schema — the same one the pipeline validates against — is the strongest
guarantee it can offer, and it catches both runner mistakes the form's own
fields miss and any drift between the form and the contract. Alternatives
rejected:

- **Form-level validation only (HTML5 constraints + ad-hoc JS):** lighter, no
  vendored validator, but it re-encodes the contract informally in field rules.
  A logic gap or a schema change the form didn't track would let an invalid file
  reach the pipeline — the exact failure this project is meant to prevent.
- **Hand-write a validator for this schema:** duplicates the contract in a
  second, drift-prone place; strictly worse than running the schema itself.

Ajv is exercised directly by the Playwright-driven tests (see ADR 001) —
the same vendored bundle validates in the browser and in CI, not a second
copy running under a different JS runtime.

## Consequences

- Ajv (~one vendored JS bundle) is a committed runtime dependency, pinned and
  updated by hand; it is the only third-party code the page loads.
- The vendored schema is inlined as `assets/schema.js` (an ES-module export) so
  validation needs no separate `fetch` of the schema file. (The page as a whole
  still needs a static server rather than `file://`, for the unrelated reason
  in ADR 001's consequences: Chrome blocks `file://` module-script loads.)
- Validation is only as current as the last `sync-contract` run. A CI drift
  check (re-running the sync and diffing) is the intended way to keep
  "vendored" from meaning "stale", but it's deferred for now: `run-drafter` is
  private, so the unauthenticated fetch CI would need 404s. Until a scoped
  token closes that gap (see the spec's manual steps), `just check-contract`
  against the sibling checkout is the only drift check, and it's manual.
- Cross-field product rules the schema can't express (date ordering, the
  health-screen consent gate, non-empty output formats) are enforced separately
  in `assemble.js` — schema validation is necessary, not sufficient.

Status: Accepted.
