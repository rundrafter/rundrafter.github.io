"""Vendor the intake contract from the upstream run-drafter repo."""

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

UPSTREAM_SIBLING = REPO_ROOT.parent / "run-drafter"
UPSTREAM_RAW_BASE = "https://raw.githubusercontent.com/eirkkr/run-drafter"

CONTRACT_FILES = ("intake-schema.json", "intake-example.json")

SOURCE_MD_TEMPLATE = """# Contract source

Vendored from the upstream `run-drafter` repo's intake contract:

- `intake-schema.json`
- `intake-example.json`

Pinned upstream revision:

revision: {revision}

Re-sync with `just sync-contract` (`uv run python scripts/sync_contract.py`).
"""


def main() -> int:
    """Sync the vendored contract, or check it for drift.

    Returns:
        Process exit code: 0 on success, 1 on drift (--check only).
    """
    args = _parse_args()
    if not args.check:
        _sync(SCHEMA_DIR, ASSETS_DIR)
        print(f"synced contract from revision {_read_pinned_revision(SCHEMA_DIR)}")
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
    return parser.parse_args()


def _sync(schema_dir: Path, assets_dir: Path) -> None:
    schema_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    revision = _fetch_contract(schema_dir)
    _write_schema_js(schema_dir, assets_dir)
    (schema_dir / "SOURCE.md").write_text(SOURCE_MD_TEMPLATE.format(revision=revision))


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
    revision = _read_pinned_revision(SCHEMA_DIR)
    for name in CONTRACT_FILES:
        url = f"{UPSTREAM_RAW_BASE}/{revision}/docs/{name}"
        with urllib.request.urlopen(url) as response:  # noqa: S310
            (dest_dir / name).write_bytes(response.read())
    return revision


def _read_pinned_revision(schema_dir: Path) -> str:
    source_md = schema_dir / "SOURCE.md"
    for line in source_md.read_text().splitlines():
        if line.startswith("revision:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError(f"no pinned revision found in {source_md}")


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
    print("contract is up to date")
    return 0


def _files_equal(a: Path, b: Path) -> bool:
    return a.is_file() and b.is_file() and a.read_bytes() == b.read_bytes()


if __name__ == "__main__":
    sys.exit(main())
