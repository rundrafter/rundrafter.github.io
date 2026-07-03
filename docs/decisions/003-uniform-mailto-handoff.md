# 003 - Uniform email handoff: download plus prefilled mailto

## Decision

After a valid submission the form hands the intake off the same way on every
device: it downloads `intake.json`, then offers one **Email it in** button that
opens the runner's mail app via a `mailto:` link, pre-addressed with a subject
and a basic message that asks them to attach the file they just downloaded. The
manual attach step is identical everywhere. The return address is also shown as
plain text, with a download-again link, as a recoverable fallback.

## Reason

A static page with no backend cannot attach a file to an email itself and cannot
send mail. Given that floor, one predictable flow beats a cleverer but uneven
one. Alternatives rejected:

- **Web Share API (`navigator.share` with files):** on supported mobile and
  some desktop browsers this genuinely opens a mail app with the file already
  attached — the thing we'd most like. Rejected because support is uneven: the
  same button would auto-attach on some devices and silently fall back to
  "attach it yourself" on others. Training runners to expect an auto-attach
  that isn't reliably there is a worse experience than one consistent manual
  step, and it doubles the code paths to test and support.
- **Embed the whole intake in the `mailto:` body:** removes the attachment
  entirely, but `mailto:` body length is client-limited and can *silently
  truncate*, sending partial intake data to the pipeline — a data-integrity
  failure worse than an honest manual attach.
- **Ask the runner to compose the email from scratch:** what the prefilled
  `mailto:` replaces; more friction and more room to send to the wrong address
  or omit context.

## Consequences

- Every successful submission involves one manual action — attaching the
  downloaded file — by design, on all platforms.
- The `mailto:` recipient and the on-screen text share a single configured
  return address; changing it is a one-place edit. That address, and the
  next-steps copy, are a required content decision before this ships.
- The subject line is composed from `runner.name` + `goal.race` so incoming
  intakes are self-labelling in the operator's inbox.
- The handoff success depends on the runner's OS having a configured mail
  client; the plain-text address + download-again link cover the case where it
  doesn't.
- If a future phase adds a backend, real server-sent email with a real
  attachment supersedes this; revisit then.

Status: Accepted.
