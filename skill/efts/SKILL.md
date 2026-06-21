---
name: efts
description: Use for Codex-only token saving, noisy terminal output, broad repo exploration, raw evidence vaulting, context compaction, A/B checks, or when the user asks for EFTS.
---

# EFTS (Effective Token Saver)

EFTS is a quality-first Codex token saver for noisy tool output, raw evidence retrieval, and targeted context packs.

## Workflow

1. Prefer targeted context packs before broad reads:
   `efts pack --query "<task or symbol>" --root .`
2. For noisy output, keep raw evidence outside chat:
   `some command | efts filter --capture --command "some command"`
3. Retrieve exact raw evidence only when needed:
   `efts get <id>` or `efts search "<term>"`
4. Find ghost-token risks:
   `efts scan --root .`
5. Prove the setup:
   `efts ab-test --fixtures benchmarks/fixtures`
   `efts watchdog --run-tests --until-pass --max-runs 5`
6. Automatic Codex Desktop compaction uses the EFTS `PostToolUse` hook installed in `%USERPROFILE%\.codex\hooks.json`.

## Reply Rules

- Be concise, but never drop file paths, commands, error text, decisions, or verification evidence.
- Never pretend compact context is complete. If the preview says `retrieval_required: true`, retrieve raw evidence with `efts get <id>`.
- Keep `AGENTS.md` as a short routing index. Move long procedures to docs and load them only when relevant.
- Keep raw outputs in SQLite, not in chat context.

## Requirement Watchdog

Use `agents/requirement-watchdog.md` for release checks. It enforces 92%+ overall saving, per-case floors, raw retrieval, redaction, Anchor recall 100%, and quality fact coverage 100%.
