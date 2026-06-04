# CCTS Requirement Watchdog

Run:

```powershell
ccts watchdog --run-tests --until-pass --max-runs 5
```

Release gates:

- Overall A/B saving must be 94% or higher on bundled fixtures.
- Per-case savings floors must pass.
- Anchor recall 100%.
- Raw retrieval success 100%.
- Secret redaction recall 100% for secret-bearing fixtures.
- Windows installer files and Codex skill files must exist.

If any gate fails, report the failing gate, exact evidence, and the smallest next fix.
