# 001 - Vanilla runtime, no build step

## Decision

The form ships as plain, hand-authored static files — `index.html`,
`assets/*.css`, `assets/*.js` (ES modules) — served exactly as written, with no
bundler, transpiler, or framework in the path that produces what the browser
loads. Local use (and tests) run it through a static file server (`just
serve`), not by opening `index.html` via `file://`.

**No node or npm anywhere in this repo, including dev/CI.** All tooling —
contract sync, the vendored Ajv bundle, and the test suite — is Python. Tests
that need to execute the shipped JS run it inside a real browser driven by
Playwright's Python bindings (`pip`-installed; it manages its own browser
binaries directly, not through npm), rather than by installing a node
runtime to run the JS in isolation.

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
- **Node in dev/CI only, for a node-based assembler unit test
  (`assemble.test.mjs` + node's Ajv):** the earlier version of this decision.
  Rejected because it still means two package ecosystems and toolchains for a
  project whose every other tool is Python (`uv`, `pytest`, `jsonschema`) —
  a second lockfile, a second `npm ci` in CI, for a test tier that Playwright
  covers anyway. Since the browser is already the source of truth for what
  ships, driving it directly (Playwright) tests the real code path instead of
  a node stand-in for it.

## Consequences

- `<script type="module">` is fetched under CORS rules, and Chrome (unlike
  Firefox) refuses that fetch for a `file://` document origin — so a page
  opened by double-clicking `index.html` silently fails to run any JS in
  Chrome. The page therefore always needs a static server, even for local use:
  `just serve` (dev) or GitHub Pages (deployed). Playwright's test browser
  loads the page the same way, over `http://`, not via `file://`.
- Repeating sections and conditional logic are more verbose in vanilla JS than
  in a framework; `assemble.js` is kept a pure, import-clean module so the
  verbosity stays testable and out of the DOM code, even though it's tested
  through a browser rather than in isolation.
- No dependency resolution or lockfile for the runtime; the one vendored runtime
  dependency (Ajv) is committed as a pinned browser bundle, fetched by URL and
  updated by hand — never `npm`-built.
- Deploy is "copy the files" — no build artifact, no CI build step to ship.
- Browser-driven tests (Playwright) are heavier and slower per test than a
  pure-function unit test would have been; that cost is accepted for staying
  single-toolchain and for testing the actual shipped DOM/Ajv/handoff wiring
  rather than `assemble.js` in isolation.
- If the form later outgrows vanilla (many more sections, shared components),
  revisiting this is a real rewrite, not an incremental change; that trade was
  accepted for phase-2 simplicity.

Status: Accepted.
