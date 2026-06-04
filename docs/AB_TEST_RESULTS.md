# CCTS A/B Test Results

Baseline sends raw terminal/file context. Optimized sends compact facts plus SQLite `ctx://` references.

- Overall baseline tokens: 22517
- Overall optimized tokens: 442
- Overall saving: 98.0%
- Anchor recall: 100%
- Runtime: 20.236 ms

| Case | Type | Baseline | Optimized | Saving | Recall |
|---|---:|---:|---:|---:|---:|
| git_status_verbose | terminal-output | 99 | 48 | 51.5% | 100% |
| long_log_with_secret | terminal-output | 20432 | 273 | 98.7% | 100% |
| pytest_failure | terminal-output | 642 | 26 | 96.0% | 100% |
| rg_results | terminal-output | 77 | 58 | 24.7% | 100% |
| symbol-pack | codex-context-pack | 1267 | 37 | 97.1% | 100% |
