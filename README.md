# CCTS - Custom Codex Token Saver

CCTS is a Codex-only token saver for Windows Codex Desktop and Codex CLI.

It replaces the older `codex-token-saver`/`cts` workflow with a global `ccts` command, a Codex skill, and a trusted `PostToolUse` hook.

## What It Does

- Stores large raw tool outputs in SQLite.
- Returns compact previews with `ctx://capture/<id>`, `sha256`, strategy, savings, and retrieval guidance.
- Keeps exact raw output retrievable with `ccts get`.
- Uses deterministic compactors for pytest, git, search, listings, build/lint output, and generic logs.
- Installs globally under `%USERPROFILE%\.codex` and `%LOCALAPPDATA%\CCTS`.
- Replaces the old `cts.cmd` with a compatibility alias that calls `ccts`.

## Install On Windows

Download or clone this repository, then double-click `install.bat` or run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

The installer writes:

- `%USERPROFILE%\.codex\bin\ccts.cmd`
- `%USERPROFILE%\.codex\bin\cts.cmd` compatibility alias
- `%USERPROFILE%\.codex\skills\custom-codex-token-saver`
- `%USERPROFILE%\.codex\hooks.json` CCTS `PostToolUse` hook
- `%LOCALAPPDATA%\CCTS`

Restart Codex Desktop after installing so the skill and hook state reload.

## Commands

```powershell
ccts pack --query "reject expired token" --root .
python -m pytest -vv | ccts filter --capture --command "python -m pytest -vv"
ccts search "expired token"
ccts get 1 --preview
ccts ab-test --fixtures benchmarks/fixtures --json docs/ab-test-results.json --markdown docs/AB_TEST_RESULTS.md
ccts watchdog --run-tests
```

## Design Boundary

CCTS is intentionally Codex-first:

- Uses `AGENTS.md`, not `CLAUDE.md`.
- Uses `~/.codex`, not `~/.claude`.
- Uses `PostToolUse` result compaction, not transparent `PreToolUse` command rewriting.
- Keeps the MCP/tool surface small.

## Verification

```powershell
python -m unittest discover -s tests -v
python -m ccts ab-test --fixtures benchmarks/fixtures
python -m ccts watchdog --run-tests
```
