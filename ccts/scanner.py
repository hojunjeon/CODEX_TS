from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .compactor import estimate_tokens
from .symbols import SKIP_DIRS


@dataclass(frozen=True)
class WasteFinding:
    path: Path
    estimated_tokens: int
    reason: str
    recommendation: str


def scan_waste(root: Path | str, limit: int = 20) -> list[WasteFinding]:
    root_path = Path(root).resolve()
    findings: list[WasteFinding] = []
    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root_path)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        tokens = estimate_tokens(text)
        reason = ""
        recommendation = ""
        name = path.name.lower()
        if tokens > 4000:
            reason = "large context file"
            recommendation = "sandbox with `ccts capture` and reference by ctx:// id"
        elif name in {"claude.md", "agents.md"} and tokens > 800:
            reason = "startup instruction overhead"
            recommendation = "move details to docs and keep AGENTS.md as a routing index"
        elif "lock" in name and tokens > 1000:
            reason = "dependency lock noise"
            recommendation = "avoid loading directly; search targeted package names"
        if reason:
            findings.append(WasteFinding(rel, tokens, reason, recommendation))
    findings.sort(key=lambda item: item.estimated_tokens, reverse=True)
    return findings[:limit]

