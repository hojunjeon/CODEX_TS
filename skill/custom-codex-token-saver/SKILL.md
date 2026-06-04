---
name: custom-codex-token-saver
description: Use for Codex-only token saving, noisy terminal output, broad repo exploration, raw evidence vaulting, context compaction, A/B checks, or when the user asks for CCTS/custom codex token saver.
---

# CCTS (Custom Codex Token Saver)

CCTS replaces the previous Codex Token Saver for this Codex installation.

## Workflow

1. Prefer targeted context packs before broad reads:
   `ccts pack --query "<task or symbol>" --root .`
2. For noisy output, keep raw evidence outside chat:
   `some command | ccts filter --capture --command "some command"`
3. Retrieve exact raw evidence only when needed:
   `ccts get <id>` or `ccts search "<term>"`
4. Find ghost-token risks:
   `ccts scan --root .`
5. Prove the setup:
   `ccts ab-test --fixtures benchmarks/fixtures`
   `ccts watchdog --run-tests --until-pass --max-runs 5`
6. Automatic Codex Desktop compaction uses the CCTS `PostToolUse` hook installed in `%USERPROFILE%\.codex\hooks.json`.

## Reply Rules

- Be concise, but never drop file paths, commands, error text, decisions, or verification evidence.
- Never pretend compact context is complete. If the preview says `retrieval_required: true`, retrieve raw evidence with `ccts get <id>`.
- Keep `AGENTS.md` as a short routing index. Move long procedures to docs and load them only when relevant.
- Keep raw outputs in SQLite, not in chat context.

## Requirement Watchdog

Use `agents/requirement-watchdog.md` for release checks. It enforces 94%+ overall saving, per-case floors, raw retrieval, redaction, and anchor recall 100%.
