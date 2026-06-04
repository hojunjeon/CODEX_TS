# CCTS Repository Analysis

CCTS is Codex-only. It borrows only the pieces that fit Codex Desktop/CLI on Windows.

| Repo | CCTS decision | Feature used |
|---|---|---|
| hojunjeon/Agents-Token-Saver | Core | Codex `PostToolUse` hook, SQLite raw vault, `ctx://capture` retrieval |
| chopratejas/headroom | Concept only | Reversible retrieval contract, not proxy/wrap MVP |
| rtk-ai/rtk | Rule source | Command output compactor ideas, not transparent command rewrite |
| tirth8205/code-review-graph | Phase 2 | Review-only graph context pack |
| mksglu/context-mode | Phase 2 | SQLite/FTS5 continuity ideas |
| alexgreensh/token-optimizer | Phase 2 | Codex doctor/dashboard ideas |
| mibayy/token-savior | Rule source | Hybrid compact fallback and manifest slimming |
| ooples/token-optimizer-mcp | Defer | Cache metrics only; large tool surface excluded |
| zilliztech/claude-context | Optional | Semantic retrieval for very large repos |
| juliusbrussee/caveman | Small rule | Concise replies while preserving evidence |
| nadimtuhin/claude-token-optimizer | Principle only | Keep AGENTS short and lazy-load docs |
| drona23/claude-token-efficient | Defer | CLAUDE.md policy does not directly fit Codex |
