# 004 - Host as an org GitHub Pages site at the root URL

## Decision

The form is served as a GitHub user/org Pages site at the root URL. A GitHub org
is created (org names may contain hyphens, so `run-drafter` →
`https://run-drafter.github.io`; fall back to `rundrafter` if that name is
taken) and this repository is transferred into it and renamed `<org>.github.io`,
so its root serves the site.

## Reason

The URL should read as `run-drafter`, not `rundrafter-webform`. With GitHub
Pages the public path is determined by how the site is hosted, so this is a
hosting-shape choice. Alternatives rejected:

- **Project Pages site (this repo as-is):** publishes to
  `eirkkr.github.io/rundrafter-webform` — the path is the repo name, which is
  the internal name we specifically don't want runners to see.
- **Custom domain:** the cleanest branding, but requires registering and paying
  for a domain plus DNS records and HTTPS provisioning — infrastructure and
  cost this zero-infra phase is trying to avoid. Left as a later option if the
  project outgrows the `github.io` URL.

An org (rather than a personal user Pages site) also gives a natural home for
the sibling `run-drafter` pipeline repo later, without another move.

## Consequences

- The repository is renamed `<org>.github.io`; its internal/project name in docs
  stays "run-drafter intake form". The local `.fieldkit` symlink is an absolute
  path and is unaffected by the rename.
- Creating the org, transferring the repo, and enabling Pages are manual,
  human-only steps (see the spec's "Manual steps"); the build does not depend on
  them until deploy (T9).
- Deploy is "push to the default branch"; Pages serves the repo root, matching
  the no-build-step runtime (ADR 001) — no build artifact to publish.
- Moving to a custom domain later is additive (a `CNAME` file + DNS) and does
  not invalidate this decision.

Status: Accepted.
