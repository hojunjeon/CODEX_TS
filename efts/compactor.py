from __future__ import annotations

from dataclasses import dataclass
import re


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", re.UNICODE)


@dataclass(frozen=True)
class CompactResult:
    text: str
    original_tokens: int
    optimized_tokens: int
    saving_ratio: float
    strategy: str


def estimate_tokens(text: str) -> int:
    """Stable local token estimate used for A/B comparisons.

    It is intentionally dependency-free. The absolute count will differ from a
    model tokenizer, but the same estimator is applied to baseline and
    optimized text so savings remain comparable.
    """

    if not text:
        return 0
    return max(1, len(TOKEN_RE.findall(text)))


def compact_output(text: str, command: str = "") -> CompactResult:
    command_l = command.lower()
    if "pytest" in command_l or "failures" in text.lower() or "passed in" in text.lower():
        compact = _compact_pytest(text)
        strategy = "pytest"
    elif command_l.strip().startswith("git diff") or text.startswith("diff --git "):
        compact = _compact_git_diff(text)
        strategy = "git-diff"
    elif command_l.strip().startswith("git status") or "changes not staged" in text.lower():
        compact = _compact_git_status(text)
        strategy = "git-status"
    elif command_l.strip().startswith(("rg ", "grep ")) or _looks_like_search_results(text):
        compact = _compact_search(text)
        strategy = "search"
    elif command_l.strip().startswith(("ls", "dir", "tree")):
        compact = _compact_listing(text)
        strategy = "listing"
    elif any(term in command_l for term in ["eslint", "tsc", "ruff", "mypy", "npm test", "pnpm test", "cargo test"]):
        compact = _compact_build_lint(text)
        strategy = "build-lint"
    else:
        compact = _compact_generic(text)
        strategy = "generic"

    original = estimate_tokens(text)
    optimized = estimate_tokens(compact)
    saving = 0.0 if original == 0 else max(0.0, 1.0 - optimized / original)
    return CompactResult(compact, original, optimized, saving, strategy)


def _strip_pytest_noise(line: str) -> str:
    line = re.sub(r"^E\s+", "", _clean_line(line))
    return line


def _clean_line(line: str) -> str:
    return line.rstrip().lstrip("\ufeff")


def _compact_pytest(text: str) -> str:
    lines = [_strip_pytest_noise(line) for line in text.splitlines()]
    kept: list[str] = []
    test_name = ""
    path_line = ""
    assert_line = ""
    summary = ""
    diagnostics = _compact_pytest_diagnostics(lines)
    for line in lines:
        clean = _clean_line(line).strip()
        if not clean:
            continue
        if clean.startswith("___") and not test_name:
            test_name = clean.strip("_ ")
        elif not path_line and re.search(r"[\w./\\-]+\.py:\d+", clean):
            path_line = clean
        elif not assert_line and re.search(r"\bassert\s+.+", clean):
            assert_line = clean
        elif not summary and re.search(r"\d+\s+failed\b|\d+\s+error", clean, re.I):
            summary = _compact_pytest_summary(clean)
        elif clean.startswith("FAILED ") and not path_line:
            path_line = clean

    kept.append("pytest:" + (f" {test_name}" if test_name else " compacted"))
    kept.extend(line for line in [path_line, assert_line, diagnostics, summary] if line)
    return _dedupe_lines(kept)


def _compact_pytest_diagnostics(lines: list[str]) -> str:
    cache = ""
    middleware: list[str] = []
    other: list[str] = []
    for line in lines:
        clean = _clean_line(line).strip()
        lower = clean.lower()
        if not clean or "verbose payload" in lower:
            continue
        if "cache hit" in lower:
            cache = re.sub(r"^debug:\s*", "", clean, flags=re.I)
        elif "middleware stack" in lower:
            match = re.search(r"middleware stack\s+(.+)$", clean, re.I)
            if match and match.group(1).strip().lower() != "start":
                middleware.append(match.group(1).strip())
        elif re.match(r"^(warning|error):", clean, re.I) or re.search(r"\b(traceback|env|config)\b", lower):
            other.append(re.sub(r"^debug:\s*", "", clean, flags=re.I))

    parts: list[str] = []
    if cache:
        parts.append(cache)
    if middleware:
        parts.append(" -> ".join(_unique(middleware[:6])))
    parts.extend(_unique(other[:3]))
    return "ctx " + "; ".join(parts) if parts else ""


def _compact_git_status(text: str) -> str:
    lines = text.splitlines()
    branch = ""
    relation = ""
    files: dict[str, list[str]] = {"M": [], "D": [], "A": [], "??": []}
    for line in lines:
        clean = _clean_line(line).strip()
        if not clean:
            continue
        if clean.startswith("On branch "):
            branch = clean.removeprefix("On branch ")
        elif "ahead of" in clean or "behind" in clean:
            relation = _compact_git_relation(clean)
        elif clean.startswith("modified:"):
            files["M"].append(clean.removeprefix("modified:").strip())
        elif clean.startswith("deleted:"):
            files["D"].append(clean.removeprefix("deleted:").strip())
        elif clean.startswith("new file:"):
            files["A"].append(clean.removeprefix("new file:").strip())
        elif re.match(r"^[\w./\\-]+\.[A-Za-z0-9]+$", clean):
            files["??"].append(clean)
    kept: list[str] = []
    if branch:
        kept.append(" ".join(part for part in ["branch", branch, relation] if part))
    for status in ["M", "D", "A", "??"]:
        if files[status]:
            kept.append(f"{status} {' '.join(_unique(files[status]))}")
    return _dedupe_lines(kept)


def _compact_git_diff(text: str) -> str:
    files: list[str] = []
    hunks: list[str] = []
    current_file = ""
    for line in text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                current_file = parts[3].removeprefix("b/")
                files.append(current_file)
        elif line.startswith(("rename from ", "rename to ", "deleted file mode", "new file mode")):
            hunks.append(_clean_line(line).strip())
        elif line.startswith("@@"):
            suffix = f" {current_file}" if current_file else ""
            hunks.append(_clean_line(line).strip() + suffix)
        elif line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            clean = _clean_line(line).strip()
            if re.search(r"assert|def |class |function |const |let |var |return |raise |throw|TODO|FIXME", clean):
                hunks.append(clean[:180])
    kept = [f"git diff: {len(_unique(files))} files", *[f"file {path}" for path in _unique(files)[:30]], *hunks[:40]]
    return _dedupe_lines(kept)


def _looks_like_search_results(text: str) -> bool:
    hits = 0
    for line in text.splitlines()[:80]:
        if re.match(r"^.+\.(py|ts|tsx|rs|go|js|jsx|java|cs|rb|php):\d+:", line) or re.match(r"^.+?\(\d+,\d+\):", line):
            hits += 1
    return hits >= 3


def _compact_search(text: str) -> str:
    hits_by_file: dict[str, list[str]] = {}
    for line in text.splitlines():
        match = re.match(r"^(.+?):(\d+):(.*)$", line)
        if not match:
            continue
        path, line_no, body = match.groups()
        hits_by_file.setdefault(path, []).append(f"{line_no}:{_clean_line(body).strip()[:140]}")
    kept = [f"search: {sum(len(v) for v in hits_by_file.values())} hits in {len(hits_by_file)} files"]
    for path, hits in list(hits_by_file.items())[:30]:
        line_nums = ",".join(hit.split(":", 1)[0] for hit in hits[:12])
        preview = hits[0].split(":", 1)[1] if hits else ""
        kept.append(f"{path}: lines {line_nums}; first {preview}")
    return _dedupe_lines(kept)


def _compact_listing(text: str) -> str:
    lines = [_clean_line(line).strip() for line in text.splitlines() if line.strip()]
    if len(lines) <= 30:
        return "\n".join(lines).strip() + "\n"
    interesting = [
        line
        for line in lines
        if re.search(r"README|AGENTS|pyproject|package\.json|Cargo\.toml|src|test|docs|\.py$|\.ts$|\.rs$", line, re.I)
    ]
    kept = [f"listing: {len(lines)} entries", *interesting[:80], f"[efts] omitted {max(0, len(lines) - len(interesting[:80]))} low-signal entries."]
    return _dedupe_lines(kept)


def _compact_build_lint(text: str) -> str:
    lines = text.splitlines()
    interesting = [
        _clean_line(line).strip()
        for line in lines
        if re.search(r"error|failed|failure|warning|\.py:\d+|\.ts:\d+|\.tsx:\d+|\.rs:\d+|exit code|summary", line, re.I)
    ]
    kept = [f"build/lint: {len(lines)} lines", *interesting[:60]]
    if len(interesting) < len(lines):
        kept.append(f"[efts] omitted {len(lines) - len(interesting)} low-signal lines.")
    return _dedupe_lines(kept)


def _compact_pytest_summary(line: str) -> str:
    clean = line.strip("= ")
    match = re.search(r"(\d+\s+failed.*?in\s+[0-9.]+s)", clean, re.I)
    if match:
        return match.group(1)
    match = re.search(r"(\d+\s+errors?.*?in\s+[0-9.]+s)", clean, re.I)
    if match:
        return match.group(1)
    return clean


def _compact_git_relation(line: str) -> str:
    match = re.search(r"\bahead of\b.+?\bby\s+(\d+)\s+commit", line)
    if match:
        return f"ahead+{match.group(1)}"
    match = re.search(r"\bbehind\b.+?\bby\s+(\d+)\s+commit", line)
    if match:
        return f"behind+{match.group(1)}"
    return line


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            out.append(item)
            seen.add(item)
    return out


def _compact_generic(text: str) -> str:
    lines = text.splitlines()
    interesting = [
        _clean_line(line).strip()
        for line in lines
        if re.search(r"error|failed|exception|traceback|warning|authorization|api[_-]?key|token|\.py:\d+|\.ts:\d+|\.rs:\d+", line, re.I)
    ]
    if len(lines) <= 24 and not interesting:
        return text.strip()
    kept = ["[efts:generic] compacted output", *lines[:6], *interesting[:24], "...", *lines[-6:]]
    return _dedupe_with_omission([_clean_line(line).strip() for line in kept if line.strip()], len(lines))


def _dedupe_with_omission(lines: list[str], original_line_count: int) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        if line not in seen:
            out.append(line)
            seen.add(line)
    omitted = max(0, original_line_count - len(out))
    if omitted:
        out.append(f"[efts] omitted {omitted} low-signal lines.")
    return "\n".join(out).strip() + "\n"


def _dedupe_lines(lines: list[str]) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        if line not in seen:
            out.append(line)
            seen.add(line)
    return "\n".join(out).strip() + "\n"

