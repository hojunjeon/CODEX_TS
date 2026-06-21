# EFTS Usage

Use EFTS whenever Codex would otherwise ingest large or noisy tool output.

## Compact Terminal Output

```powershell
python -m pytest -vv | efts filter --capture --command "python -m pytest -vv"
```

The compact output preserves anchors, diagnostic facts, and stores exact raw output in SQLite.

For pytest failures, EFTS keeps the failing test, file/line, assertion, summary, and compact middleware/cache context when present.

## Retrieve Raw Evidence

```powershell
efts get 1
efts get 1 --preview
efts search "AssertionError"
```

## Install Hook

The Windows installer runs this automatically:

```powershell
efts install-hook --codex-home "$env:USERPROFILE\.codex" --db "$env:LOCALAPPDATA\EFTS\context.sqlite"
```

## Project Routing

Keep project `AGENTS.md` short:

```powershell
efts init --root .
```

## Quality Gate

```powershell
efts ab-test --fixtures benchmarks/fixtures
efts watchdog --run-tests
```

The bundled gate requires 92%+ overall saving, 100% anchor recall, and 100% quality fact coverage on the bundled fixtures.
