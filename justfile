# List available commands.
default:
    @just --list

# Lint all markdown.
check:
    uvx rumdl@0.2.26 check .

# Auto-fix markdown issues.
fix:
    uvx rumdl@0.2.26 check --fix .
