# List available commands.
default:
    @just --list

# Run static checks (markdown lint).
lint:
    uvx rumdl@0.2.26 check .

# Auto-fix markdown issues.
fix:
    uvx rumdl@0.2.26 check --fix .

# Vendor the intake contract (schema + example) from upstream rundrafter.
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

# Run all checks (lint + test).
check: lint test
