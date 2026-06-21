# EFTS - Effective Token Saver

EFTS is a Codex-only token saver for Windows Codex Desktop and Codex CLI.

It replaces the older `codex-token-saver`/`cts` workflow with a global `efts` command, a Codex skill, and a trusted `PostToolUse` hook.

## What It Does

- Stores large raw tool outputs in SQLite.
- Returns compact previews with `ctx://capture/<id>`, `sha256`, strategy, savings, and retrieval guidance.
- Keeps exact raw output retrievable with `efts get`.
- Uses deterministic compactors for pytest, git, search, listings, build/lint output, and generic logs.
- Preserves debugging facts such as failing tests, assertions, middleware/cache context, and related code symbols.
- Measures `quality_fact_coverage` alongside token savings so quality regressions are visible.
- Installs globally under `%USERPROFILE%\.codex` and `%LOCALAPPDATA%\EFTS`.
- Removes the old CCTS command, skill, and hook from active Codex paths.

## Install On Windows

Download or clone this repository, then double-click `install.bat` or run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

The installer writes:

- `%USERPROFILE%\.codex\bin\efts.cmd`
- `%USERPROFILE%\.codex\skills\efts`
- `%USERPROFILE%\.codex\hooks.json` EFTS `PostToolUse` hook
- `%LOCALAPPDATA%\EFTS`

Restart Codex Desktop after installing so the skill and hook state reload.

## Commands

```powershell
efts pack --query "reject expired token" --root .
python -m pytest -vv | efts filter --capture --command "python -m pytest -vv"
efts search "expired token"
efts get 1 --preview
efts ab-test --fixtures benchmarks/fixtures --json docs/ab-test-results.json --markdown docs/AB_TEST_RESULTS.md
efts watchdog --run-tests
```

Current bundled gate:

- Overall saving >= 92%
- Anchor recall = 100%
- Quality fact coverage = 100%
- Per-case floors for git status, pytest, and symbol packs

## Design Boundary

EFTS is intentionally Codex-first:

- Uses `AGENTS.md`, not `CLAUDE.md`.
- Uses `~/.codex`, not `~/.claude`.
- Uses `PostToolUse` result compaction, not transparent `PreToolUse` command rewriting.
- Keeps the MCP/tool surface small.

## Verification

```powershell
python -m unittest discover -s tests -v
python -m efts ab-test --fixtures benchmarks/fixtures
python -m efts watchdog --run-tests
```
