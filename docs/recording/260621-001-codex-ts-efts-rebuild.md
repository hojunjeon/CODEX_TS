# 260621-001 codex-ts efts rebuild

Date: 2026-06-21
Project: CODEX_TS
Status: EFTS installed locally with config-parse prevention; paused before destructive remote push confirmation

## Purpose

- Replace the prior CCTS surface with `efts` (effective token saver).
- Preserve token savings while improving result quality through explicit quality fact coverage gates.
- Prepare the local repository for a push that replaces the remote `main` tree.

## Scope

- Renamed Python package and CLI from `ccts` to `efts`.
- Renamed the Codex skill folder from `custom-codex-token-saver` to `efts`.
- Removed generated distribution/output artifacts from version control.
- Updated docs, install scripts, tests, fixtures, and benchmark reports for EFTS.
- Removed active CCTS command, skill, and hook from the user's Codex home.
- Fixed a Codex Desktop restart failure caused by duplicate `hooks.state` TOML tables.

## Changed Files

- `efts/*`
- `tests/test_efts_core.py`
- `skill/efts/*`
- `README.md`
- `docs/USAGE.md`
- `docs/AB_TEST_RESULTS.md`
- `docs/ab-test-results.json`
- `docs/WATCHDOG_REPORT.md`
- `install.ps1`
- `install.bat`
- `benchmarks/fixtures/*`

## Key Decisions

- Do not use CCTS/CTS during development; use direct Python commands and focused shell checks.
- Keep legacy hook cleanup only where needed to remove old installed hook files.
- Use quality fact coverage as a first-class A/B metric, not only recall and token savings.
- Remove generated zip/output artifacts from the repo instead of renaming them.
- Do not keep a `cts.cmd` compatibility alias; legacy CCTS paths must be inactive.
- Archive removed legacy Codex files under `C:\Users\user\.codex\backups\efts-migration` instead of deleting without recovery.
- Rewrite `post_tool_use` trust-state sections canonically during install; do not append new double-quoted keys beside old single-quoted keys.
- Trust only managed EFTS and OMX PostToolUse hooks after removing legacy CCTS entries.

## Commands

- `git clone https://github.com/hojunjeon/CODEX_TS.git CODEX_TS`
- `python -m unittest discover -s tests -v`
- `python -m efts ab-test --fixtures benchmarks\fixtures --json docs\ab-test-results.json --markdown docs\AB_TEST_RESULTS.md`
- `python -m efts watchdog --run-tests --output docs\WATCHDOG_REPORT.md`
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1`
- `C:\Users\user\.codex\bin\efts.cmd ab-test --fixtures C:\Users\user\AppData\Local\EFTS\benchmarks\fixtures`
- `rg -n "codex-token-saver|custom-codex-token-saver|cts\.cmd|CCTS|ccts" C:\Users\user\.codex\bin C:\Users\user\.codex\hooks C:\Users\user\.codex\skills\efts C:\Users\user\.codex\hooks.json C:\Users\user\.codex\config.toml`
- `codex doctor --summary --ascii`
- `python - <<'PY' ... tomllib.loads(config.toml) ... PY`
- `rg -n -i "Invalid TOML|sandbox|permissionProfile|settings-store|failed" C:\Users\user\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\Codex\Logs\2026\06\21\codex-desktop-40ed914f-b8bc-4a70-9b37-436b38d71653-29676-t0-i1-074826-0.log`
- `rg -n "sk-[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._~+/=-]{12,}|ghp_[A-Za-z0-9_]{12,}|api[_-]?key\s*[:=]|password\s*[:=]|secret\s*[:=]" -g '!*.pyc' -g '!benchmarks/fixtures/.ab/**'`
- `rg -n "CCTS|ccts|custom-codex-token-saver|Custom Codex Token Saver" -g '!*.pyc' -g '!benchmarks/fixtures/.ab/**'`

## Verification

- Unit tests: PASS, 6 tests including legacy CCTS hook removal and trust-state TOML parsing.
- A/B benchmark: PASS, saving 97.8%, recall 100%, quality 100%, elapsed 18.276ms.
- Watchdog: PASS, all gates including saving floor, recall, quality, symbol floor, docs, and tests.
- Installed EFTS command: PASS, `C:\Users\user\.codex\bin\efts.cmd` A/B saving 97.8%, recall 100%, quality 100%.
- Active CCTS removal: PASS, no `cts.cmd`, no `skills\codex-token-saver`, no legacy CCTS hook shim, no `AppData\Local\CodexTokenSaver`, and no CCTS references in active Codex hook/config/efts skill paths.
- Codex config parse: PASS, `tomllib.loads(C:\Users\user\.codex\config.toml)` succeeded.
- Codex doctor: PASS, `17 ok | 1 idle | 1 notes | 0 warn | 0 fail`.
- Desktop log check: PASS, latest checked Desktop log had normal `permissionProfile/list` and `windowsSandbox/readiness` responses; the earlier failing log showed duplicate `hooks.state."...post_tool_use:0:0"` as the root cause.
- Secret-like scan: PASS, no matches after replacing fixture tokens with fake values.
- Name trace: PASS, only intentional legacy hook cleanup references remain.

## Remaining Risks

- Remote `main` push is intentionally paused because it replaces/deletes the old repository tree.
- `gh` CLI is unavailable, so publish uses `git push` only.
- CRLF warnings are present on Windows but did not affect tests.
- Existing Codex Desktop sessions may need restart before the newly installed EFTS skill/hook list is fully reloaded.

## Next Step

- After explicit user confirmation, push the commit to `origin/main`.
