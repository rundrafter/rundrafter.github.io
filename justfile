# List available commands.
default:
    @just --list

# Lint all markdown.
check:
    uvx rumdl@0.2.26 check .

# Auto-fix markdown issues.
fix:
    uvx rumdl@0.2.26 check --fix .

# Vendor the intake contract (schema + example) from upstream run-drafter.
sync-contract:
    uv run python scripts/sync_contract.py

# Check the vendored contract for drift against upstream, without writing.
check-contract:
    uv run python scripts/sync_contract.py --check

# Serve the form locally.
serve:
    uv run python -m http.server 8000

# Run the test suite.
test:
    uv run pytest
