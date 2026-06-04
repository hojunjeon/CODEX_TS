# CCTS Usage

Use CCTS whenever Codex would otherwise ingest large or noisy tool output.

## Compact Terminal Output

```powershell
python -m pytest -vv | ccts filter --capture --command "python -m pytest -vv"
```

The compact output preserves anchors and stores exact raw output in SQLite.

## Retrieve Raw Evidence

```powershell
ccts get 1
ccts get 1 --preview
ccts search "AssertionError"
```

## Install Hook

The Windows installer runs this automatically:

```powershell
ccts install-hook --codex-home "$env:USERPROFILE\.codex" --db "$env:LOCALAPPDATA\CCTS\context.sqlite"
```

## Project Routing

Keep project `AGENTS.md` short:

```powershell
ccts init --root .
```
