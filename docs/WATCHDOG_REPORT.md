# EFTS Requirement Watchdog

| Gate | Status | Evidence |
|---|---|---|
| 10 repo analysis | PASS | docs\REPO_ANALYSIS.md |
| Codex skill and AGENTS workflow | PASS | skill\efts\SKILL.md |
| requirement watchdog subagent | PASS | skill\efts\agents\requirement-watchdog.md |
| Codex PostToolUse hook | PASS | efts\hook.py, tests\test_efts_core.py |
| one-click Windows installer | PASS | install.bat, install.ps1 |
| A/B token saving with quality preservation | PASS | A/B saving=97.8%>=92%, recall=100%, quality=100% |
| A/B benchmark runtime | PASS | elapsed=20.840ms<=1000ms |
| per-case Codex savings floors | PASS | git_status_verbose=52.0%>=50%; pytest_failure=93.6%>=85%; symbol-pack=94.4%>=94% |
| docs and benchmark report | PASS | README.md, docs\USAGE.md, docs\AB_TEST_RESULTS.md |
| automated tests | PASS | unittest discover rc=0 |
