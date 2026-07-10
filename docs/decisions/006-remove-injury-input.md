# 006 - Remove the injury-history section and `build_mode`

## Decision

Drop the Injuries section (`injuries[]` - repeating body-area/severity/notes
entries) and the `preferences.build_mode` radio fieldset from the form,
`assemble.js`, and the vendored contract. Adjust the taper-explanation and
privacy/handoff copy that referenced injury-driven caution, since
RunDrafter no longer derives a caution flag from injury history.

## Reason

This mirrors upstream `rundrafter`'s own removal - see its ADR 009 for the
full reasoning (the injury -> free-text sub-step -> `build_mode` ->
`injury_caution` cascade was the one automated safety check the pipeline
ran, removed because it collected self-reported, un-acted-upon health data
for a downgrade behaviour a human plan reviewer can apply directly). This
repo has no separate stance to litigate: `schema/intake-schema.json` now
rejects both `injuries` and `build_mode` outright
(`additionalProperties: false`), so a form that kept asking for either would
produce intakes the pipeline bounces.

`build_mode` *was* collected client-side (a "Let RunDrafter decide" /
"Standard" / "Cautious" radio fieldset) - the vendored contract was simply
stale at the time this ADR was first drafted, still pinned to a pre-removal
upstream revision. Re-running `just sync-contract` against upstream's
current `main` surfaced the drift and pulled `build_mode` out of the
vendored schema automatically; the client-side fieldset and its handling
still needed the same manual removal as `injuries`.

## Consequences

- `schema/intake-schema.json`, `schema/intake-example.json`, and
  `assets/schema.js` were re-vendored via `just sync-contract` rather than
  hand-edited (see `schema/SOURCE.md`).
- `index.html` drops the `#injuries-list` section, `#add-injury` button, and
  `injury-template`, and the "Build mode" radio fieldset; `assets/form.js`
  drops the `setupRepeatingGroup("injuries-list", ...)` call;
  `assets/assemble.js` drops the `injuries` prune/spread (`build_mode` was
  already handled generically as part of `preferences`, so no code change
  was needed there beyond the HTML).
- `index.html`'s taper-explanation copy no longer promises injury-aware
  caution; the privacy/handoff note no longer lists injury data among what's
  collected.
- `docs/architecture.md`'s field-inventory table is updated to match.
- `tests/test_assemble.py`'s injuries-related assertions and fixtures are
  updated to match.
- `rules_revision` in `schema/SOURCE.md` is re-pinned to the upstream commit
  that removed the injury-caution cascade from `validate.py`/`schedule.py`/
  `review.py`, per the parity workflow in `CLAUDE.md`.

Status: Accepted.
