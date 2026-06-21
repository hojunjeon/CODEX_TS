# EFTS A/B Test Results

Baseline sends raw terminal/file context. Optimized sends compact facts plus SQLite `ctx://` references.

- Overall baseline tokens: 22521
- Overall optimized tokens: 506
- Overall saving: 97.8%
- Anchor recall: 100%
- Quality fact coverage: 100%
- Runtime: 18.276 ms

| Case | Type | Baseline | Optimized | Saving | Recall | Quality |
|---|---:|---:|---:|---:|---:|---:|
| git_status_verbose | terminal-output | 100 | 48 | 52.0% | 100% | 100% |
| long_log_with_secret | terminal-output | 20431 | 271 | 98.7% | 100% | 100% |
| pytest_failure | terminal-output | 643 | 41 | 93.6% | 100% | 100% |
| rg_results | terminal-output | 78 | 75 | 3.9% | 100% | 100% |
| symbol-pack | codex-context-pack | 1269 | 71 | 94.4% | 100% | 100% |
