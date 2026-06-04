from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".rs",
    ".go",
    ".java",
    ".cs",
    ".rb",
    ".php",
    ".md",
}

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".custom-codex-token-saver",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "target",
    "research",
    "devlog",
}


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    path: Path
    start_line: int
    end_line: int
    source: str


def iter_source_files(root: Path) -> list[Path]:
    root = root.resolve()
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        if path.suffix.lower() in SOURCE_EXTENSIONS:
            files.append(path)
    return sorted(files)


def extract_symbols(path: Path, root: Path | None = None) -> list[Symbol]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    rel_path = path if root is None else path.relative_to(root)
    candidates: list[tuple[str, str, int]] = []
    patterns = _patterns_for(path.suffix.lower())
    for idx, line in enumerate(lines, start=1):
        for kind, pattern in patterns:
            match = pattern.search(line)
            if match:
                candidates.append((match.group(1), kind, idx))
                break

    symbols: list[Symbol] = []
    for pos, (name, kind, start) in enumerate(candidates):
        next_start = candidates[pos + 1][2] if pos + 1 < len(candidates) else len(lines) + 1
        end = max(start, min(next_start - 1, start + 80))
        source = "\n".join(lines[start - 1 : end]).strip()
        symbols.append(Symbol(name=name, kind=kind, path=rel_path, start_line=start, end_line=end, source=source))
    return symbols


def _patterns_for(suffix: str) -> list[tuple[str, re.Pattern[str]]]:
    if suffix == ".py":
        return [
            ("class", re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)")),
            ("function", re.compile(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)")),
        ]
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        return [
            ("class", re.compile(r"\bclass\s+([A-Za-z_$][A-Za-z0-9_$]*)")),
            ("function", re.compile(r"\bfunction\s+([A-Za-z_$][A-Za-z0-9_$]*)")),
            ("function", re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?\(?")),
            ("function", re.compile(r"^\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*[:=]\s*(?:async\s*)?\(")),
        ]
    if suffix == ".rs":
        return [
            ("function", re.compile(r"\bfn\s+([A-Za-z_][A-Za-z0-9_]*)")),
            ("struct", re.compile(r"\bstruct\s+([A-Za-z_][A-Za-z0-9_]*)")),
            ("enum", re.compile(r"\benum\s+([A-Za-z_][A-Za-z0-9_]*)")),
        ]
    if suffix == ".go":
        return [("function", re.compile(r"\bfunc\s+(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)"))]
    if suffix in {".java", ".cs"}:
        return [
            ("class", re.compile(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)")),
            ("function", re.compile(r"\b(?:public|private|protected|static|\s)+[A-Za-z0-9_<>\[\]]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")),
        ]
    if suffix == ".md":
        return [("section", re.compile(r"^#{1,6}\s+(.+?)\s*$"))]
    return [("symbol", re.compile(r"^\s*(?:function|class|def)\s+([A-Za-z_][A-Za-z0-9_]*)"))]

