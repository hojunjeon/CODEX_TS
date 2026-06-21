from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .compactor import estimate_tokens
from .store import ContextStore
from .symbols import Symbol, extract_symbols, iter_source_files


@dataclass(frozen=True)
class RawRef:
    capture_id: int
    path: Path


@dataclass(frozen=True)
class ContextPack:
    text: str
    baseline_tokens: int
    optimized_tokens: int
    saving_ratio: float
    anchor_recall: float
    raw_refs: list[RawRef]


class ContextPacker:
    def __init__(self, root: Path | str, store: ContextStore):
        self.root = Path(root).resolve()
        self.store = store

    def build_pack(self, query: str, token_budget: int = 1200) -> ContextPack:
        files = iter_source_files(self.root)
        file_texts: list[tuple[Path, str]] = []
        for path in files:
            try:
                file_texts.append((path, path.read_text(encoding="utf-8")))
            except UnicodeDecodeError:
                file_texts.append((path, path.read_text(encoding="utf-8", errors="replace")))
        baseline_text = "\n".join(text for _, text in file_texts)
        baseline_tokens = estimate_tokens(baseline_text)

        symbols: list[Symbol] = []
        for path, _ in file_texts:
            symbols.extend(extract_symbols(path, self.root))

        terms = _terms(query)
        scored = sorted(
            ((self._score_symbol(symbol, query), _term_coverage(symbol, terms), symbol) for symbol in symbols),
            key=lambda item: (-item[1], -item[0], str(item[2].path), item[2].start_line),
        )
        min_coverage = min(2, len(terms)) if terms else 0
        selected = [symbol for score, coverage, symbol in scored if score > 0 and coverage >= min_coverage][:8]
        if not selected:
            selected = [symbol for score, _coverage, symbol in scored if score > 0][:8]
        if not selected and symbols:
            selected = symbols[: min(5, len(symbols))]
        selected = _expand_related_symbols(selected, symbols, terms)

        raw_refs: list[RawRef] = []
        captured_paths: set[Path] = set()
        captures_by_path: dict[Path, int] = {}
        chunks = [f"q {query}"]
        current_tokens = estimate_tokens("\n".join(chunks))
        included = 0
        for symbol in selected:
            full_path = self.root / symbol.path
            if symbol.path not in captured_paths:
                raw_text = full_path.read_text(encoding="utf-8", errors="replace")
                cap = self.store.capture("Read", raw_text, command=f"pack {symbol.path}")
                raw_refs.append(RawRef(cap.id, symbol.path))
                captured_paths.add(symbol.path)
                captures_by_path[symbol.path] = cap.id
            else:
                cap_id = captures_by_path[symbol.path]
                cap = self.store.get(cap_id)

            snippet = f"{_compact_kind(symbol.kind)} {symbol.name} {symbol.path}:{symbol.start_line} ctx://capture/{cap.id}\n{_symbol_excerpt(symbol, query)}"
            needed = estimate_tokens(snippet)
            if current_tokens + needed > token_budget and included:
                break
            chunks.append(snippet)
            current_tokens += needed
            included += 1

        pack_text = "\n".join(chunks).strip() + "\n"
        optimized_tokens = estimate_tokens(pack_text)
        saving = 0.0 if baseline_tokens == 0 else max(0.0, 1.0 - optimized_tokens / baseline_tokens)
        recall = _anchor_recall(query, "\n".join(chunks[1:]))
        return ContextPack(pack_text, baseline_tokens, optimized_tokens, saving, recall, raw_refs)

    def _score_symbol(self, symbol: Symbol, query: str) -> int:
        terms = _terms(query)
        name_haystack = symbol.name.lower().replace("_", " ")
        haystack = " ".join([name_haystack, str(symbol.path), symbol.source]).lower().replace("_", " ")
        score = 0
        for term in terms:
            if _term_hit(term, name_haystack):
                score += 4
            if _term_hit(term, haystack):
                score += 1
        return score


def _terms(query: str) -> list[str]:
    return [term.lower() for term in re.findall(r"[A-Za-z0-9_]+", query) if len(term) > 2]


def _compact_kind(kind: str) -> str:
    return {
        "function": "fn",
        "class": "cls",
        "section": "sec",
        "struct": "struct",
        "enum": "enum",
    }.get(kind, kind)


def _term_coverage(symbol: Symbol, terms: list[str]) -> int:
    haystack = " ".join([symbol.name.replace("_", " "), str(symbol.path), symbol.source]).lower().replace("_", " ")
    return sum(1 for term in terms if _term_hit(term, haystack))


def _anchor_recall(query: str, text: str) -> float:
    terms = _terms(query)
    if not terms:
        return 1.0
    normalized = text.lower().replace("_", " ")
    hits = sum(1 for term in terms if _term_hit(term, normalized))
    return hits / len(terms)


def _expand_related_symbols(selected: list[Symbol], symbols: list[Symbol], terms: list[str], limit: int = 10) -> list[Symbol]:
    if not selected:
        return selected
    by_path: dict[Path, list[Symbol]] = {}
    for symbol in symbols:
        by_path.setdefault(symbol.path, []).append(symbol)

    chosen: dict[tuple[Path, int, str], Symbol] = {}

    def add(symbol: Symbol) -> None:
        chosen[(symbol.path, symbol.start_line, symbol.name)] = symbol

    min_related_coverage = max(1, min(2, len(terms))) if terms else 1
    for symbol in selected:
        add(symbol)
        same_file = by_path.get(symbol.path, [])
        try:
            index = same_file.index(symbol)
        except ValueError:
            index = -1
        if index > 0:
            for candidate in reversed(same_file[:index]):
                if candidate.kind == "class":
                    add(candidate)
                    break
        for candidate in same_file:
            if candidate == symbol:
                continue
            if _term_coverage(candidate, terms) >= min_related_coverage:
                add(candidate)

    return sorted(chosen.values(), key=lambda symbol: (str(symbol.path), symbol.start_line))[:limit]


def _term_hit(term: str, haystack: str) -> bool:
    if term in haystack:
        return True
    variants = {term}
    if term.endswith("ed") and len(term) > 4:
        variants.add(term[:-2])
    if term.endswith("ing") and len(term) > 5:
        variants.add(term[:-3])
    if term.endswith("s") and len(term) > 4:
        variants.add(term[:-1])
    return any(len(variant) >= 3 and variant in haystack for variant in variants)


def _symbol_excerpt(symbol: Symbol, query: str, max_lines: int = 8) -> str:
    lines = [line.rstrip() for line in symbol.source.splitlines() if line.strip()]
    if symbol.kind == "class" and len(lines) == 1:
        return ""
    evidence_lines = lines[1:] or lines
    guard_summary = _compact_guard_raise(evidence_lines)
    if guard_summary:
        return f"  {guard_summary}"
    if len(evidence_lines) <= max_lines:
        return "\n".join(f"  {line}" for line in evidence_lines)

    terms = _terms(query)
    selected: list[str] = []
    for line in evidence_lines:
        haystack = line.lower().replace("_", " ")
        if any(term in haystack for term in terms):
            selected.append(line)
        if len(selected) >= max_lines:
            break

    if not selected:
        selected.extend(evidence_lines[:max_lines])
    return "\n".join(f"  {line}" for line in selected[:max_lines])


def _compact_guard_raise(lines: list[str]) -> str:
    if len(lines) != 2:
        return ""
    first = lines[0].strip()
    second = lines[1].strip()
    if not first.startswith("if ") or not first.endswith(":") or not second.startswith("raise "):
        return ""
    condition = first.removeprefix("if ").removesuffix(":").strip()
    raised = second.removeprefix("raise ").strip()
    message = re.search(r"[\"'](.+?)[\"']", raised)
    if message:
        raised = message.group(1)
    return f"{condition} => {raised}"

