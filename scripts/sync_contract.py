"""Vendor the intake contract from the upstream rundrafter repo."""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schema"
ASSETS_DIR = REPO_ROOT / "assets"
SOURCE_MD = SCHEMA_DIR / "SOURCE.md"

UPSTREAM_SIBLING = REPO_ROOT.parent / "rundrafter"
UPSTREAM_RAW_BASE = "https://raw.githubusercontent.com/rundrafter/rundrafter"

CONTRACT_FILES = ("intake-schema.json", "intake-example.json")

# Not vendored (they're a private repo's internals, reflected here only as
# client-side JS in assets/assemble.js) - just hash-pinned, so a rule change
# upstream shows up as drift instead of silently diverging. See
# docs/architecture.md's "Rules the schema can't express".
RULES_FILES = ("src/rundrafter/validate.py", "docs/spec/contracts.md")

SOURCE_MD_TEMPLATE = """# Contract source

Vendored from the upstream `rundrafter` repo's intake contract:

- `intake-schema.json`
- `intake-example.json`

Pinned upstream revision:

revision: {revision}

Re-sync with `just sync-contract` (`uv run python scripts/sync_contract.py`).

## Cross-field rule parity

The cross-field rules in `assets/assemble.js` mirror upstream
`src/rundrafter/validate.py` (constraints documented in
`docs/spec/contracts.md`). These aren't vendored - only their upstream
revision is pinned, checked by `just check-contract` against the sibling
checkout.

rules_revision: {rules_revision}

After syncing assemble.js (and docs/architecture.md) to a rule change
upstream, run `uv run python scripts/sync_contract.py --update-rules-revision`
(sibling checkout required) to record the new pin.
"""


def main() -> int:
    """Sync the vendored contract, check it for drift, or re-pin the rules
    revision after a manual parity review.

    Returns:
        Process exit code: 0 on success, 1 on drift (--check only).
    """
    args = _parse_args()
    if args.update_rules_revision:
        _update_rules_revision()
        return 0

    if not args.check:
        _sync(SCHEMA_DIR, ASSETS_DIR)
        print(f"synced contract from revision {_read_pinned(SCHEMA_DIR, 'revision')}")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        tmp_schema_dir = Path(tmp) / "schema"
        tmp_assets_dir = Path(tmp) / "assets"
        _sync(tmp_schema_dir, tmp_assets_dir)
        return _check_drift(tmp_schema_dir, tmp_assets_dir)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="sync into a temp dir and diff against the committed copies; "
        "don't write anything (used by CI to detect contract drift)",
    )
    parser.add_argument(
        "--update-rules-revision",
        action="store_true",
        help="record the sibling checkout's current revision of "
        "validate.py + contracts.md as the new parity pin, once "
        "assemble.js has been synced to match a rule change upstream",
    )
    return parser.parse_args()


def _sync(schema_dir: Path, assets_dir: Path) -> None:
    schema_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    # A schema-only resync doesn't touch rule parity; carry the existing pin
    # forward (or bootstrap it to the schema revision the first time).
    revision = _fetch_contract(schema_dir)
    rules_revision = revision
    if SOURCE_MD.is_file():
        rules_revision = _read_pinned(SCHEMA_DIR, "rules_revision", default=revision)
    _write_schema_js(schema_dir, assets_dir)
    (schema_dir / "SOURCE.md").write_text(
        SOURCE_MD_TEMPLATE.format(revision=revision, rules_revision=rules_revision)
    )


def _update_rules_revision() -> None:
    if not UPSTREAM_SIBLING.is_dir():
        raise SystemExit(
            "--update-rules-revision requires a ../rundrafter sibling checkout"
        )
    revision = _read_pinned(SCHEMA_DIR, "revision")
    rules_revision = _current_rules_revision()
    SOURCE_MD.write_text(
        SOURCE_MD_TEMPLATE.format(revision=revision, rules_revision=rules_revision)
    )
    print(f"rules_revision pinned to {rules_revision}")


def _fetch_contract(dest_dir: Path) -> str:
    if UPSTREAM_SIBLING.is_dir():
        return _sync_from_sibling(dest_dir)
    return _sync_from_github(dest_dir)


def _sync_from_sibling(dest_dir: Path) -> str:
    docs_dir = UPSTREAM_SIBLING / "docs"
    for name in CONTRACT_FILES:
        shutil.copy(docs_dir / name, dest_dir / name)
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", *(f"docs/{n}" for n in CONTRACT_FILES)],
        cwd=UPSTREAM_SIBLING,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _sync_from_github(dest_dir: Path) -> str:
    revision = _read_pinned(SCHEMA_DIR, "revision")
    for name in CONTRACT_FILES:
        url = f"{UPSTREAM_RAW_BASE}/{revision}/docs/{name}"
        with urllib.request.urlopen(url) as response:  # noqa: S310
            (dest_dir / name).write_bytes(response.read())
    return revision


def _current_rules_revision() -> str:
    """The sibling checkout's current git hash for the rule-source files."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", *RULES_FILES],
        cwd=UPSTREAM_SIBLING,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _read_pinned(schema_dir: Path, label: str, default: str | None = None) -> str:
    source_md = schema_dir / "SOURCE.md"
    for line in source_md.read_text().splitlines():
        if line.startswith(f"{label}:"):
            return line.split(":", 1)[1].strip()
    if default is not None:
        return default
    raise RuntimeError(f"no pinned {label} found in {source_md}")


def _write_schema_js(schema_dir: Path, assets_dir: Path) -> None:
    schema = json.loads((schema_dir / "intake-schema.json").read_text())
    js = "export default " + json.dumps(schema, indent=2) + ";\n"
    (assets_dir / "schema.js").write_text(js)


def _check_drift(tmp_schema_dir: Path, tmp_assets_dir: Path) -> int:
    stale = [
        path
        for path in (
            "schema/intake-schema.json",
            "schema/intake-example.json",
            "schema/SOURCE.md",
            "assets/schema.js",
        )
        if not _files_equal(Path(tmp_schema_dir.parent, path), REPO_ROOT / path)
    ]
    if stale:
        print("contract drift detected in: " + ", ".join(stale), file=sys.stderr)
        print("run `just sync-contract`", file=sys.stderr)
        return 1

    rules_drift = _check_rules_drift()
    if rules_drift:
        print(rules_drift, file=sys.stderr)
        return 1

    print("contract is up to date")
    return 0


def _check_rules_drift() -> str | None:
    """Compare the pinned rules_revision against the sibling's current one.

    Returns:
        A message describing the drift, or ``None`` if there's no sibling to
        check against (this repo can't reach the private upstream over
        GitHub in CI, so it's skipped rather than failed) or nothing has
        drifted.
    """
    if not UPSTREAM_SIBLING.is_dir():
        return None
    pinned = _read_pinned(SCHEMA_DIR, "rules_revision")
    current = _current_rules_revision()
    if pinned == current:
        return None
    return (
        f"rules changed upstream since last parity sync ({pinned} -> {current}): "
        "diff validate.py/contracts.md against assets/assemble.js + "
        "docs/architecture.md, run tests/test_stage1_parity.py, then "
        "`uv run python scripts/sync_contract.py --update-rules-revision`"
    )


def _files_equal(a: Path, b: Path) -> bool:
    return a.is_file() and b.is_file() and a.read_bytes() == b.read_bytes()


if __name__ == "__main__":
    sys.exit(main())
