# 001 - Vanilla runtime, no build step

## Decision

The form ships as plain, hand-authored static files — `index.html`,
`assets/*.css`, `assets/*.js` (ES modules) — served exactly as written and
openable from `file://`. There is no bundler, transpiler, or framework in the
path that produces what the browser loads.

Node is permitted only in *dev/CI tooling* — the contract-sync script and the
assembler tests — and never in the shipped artifact.

## Reason

Phase 2 is a zero-infrastructure, product-facing surface that depends on
RunDrafter only through the intake contract. Keeping the runtime toolchain-free
matches that ethos: the page can be opened locally, deployed by copying files to
GitHub Pages, and read without a build graph in the way. Alternatives rejected:

- **Vite + a component framework (Svelte/React):** cleaner code for a large
  form with repeating and conditional sections, but it drags a full JS
  toolchain and a build-to-deploy pipeline into an otherwise Python-only,
  zero-infra project — a standing dependency and a ship-path build step, bought
  for authoring convenience the vanilla version can live without.
- **A small bundler step (esbuild/rollup) with vanilla source:** still a
  build in the ship path, for a page whose assets are already small and
  hand-maintainable.

The one concession is node in dev/CI: the assembler is validated with the same
Ajv + schema the browser runs (see ADR 002), which needs a JS runtime in tests.
This ships nothing.

## Consequences

- Repeating sections and conditional logic are more verbose in vanilla JS than
  in a framework; `assemble.js` is kept a pure, import-clean module so the
  verbosity stays testable and out of the DOM code.
- No dependency resolution or lockfile for the runtime; the one vendored runtime
  dependency (Ajv) is committed as a pinned browser bundle, updated by hand.
- Deploy is "copy the files" — no build artifact, no CI build step to ship.
- If the form later outgrows vanilla (many more sections, shared components),
  revisiting this is a real rewrite, not an incremental change; that trade was
  accepted for phase-2 simplicity.

Status: Accepted.
