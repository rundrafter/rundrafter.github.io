# Ajv bundle source

`ajv.bundle.js` is the standalone UMD browser build of Ajv (the `ajv-dist`
package), fetched by URL and committed by hand — no npm/node involved in
producing it (see rundrafter's ADR 025). Uses the `ajv2020` build
specifically, because the vendored intake schema declares
`$schema: .../2020-12/schema`; the plain `ajv7` build only understands
draft-07 and rejects it with "no schema with key or ref" at compile time.

- Source: `https://cdnjs.cloudflare.com/ajax/libs/ajv/8.17.1/ajv2020.min.js`
- Pinned version: 8.17.1
- SRI (sha512): `p5sFpd2pipqqvDr+bipEI4bGzNEE24IPv3NQtNcQeh+FAnFKBD8JaUpmKfoznN3vi2SGBEFusWxWARbfDyYjtg==`

Exposes a global `ajv2020`; the constructor is `ajv2020.default` (or
`ajv2020.Ajv2020`).

To update: fetch the URL above at a newer version, verify the SRI hash
published by cdnjs for that version, and overwrite this file's pinned
version/hash together with `assets/ajv.bundle.js`.
