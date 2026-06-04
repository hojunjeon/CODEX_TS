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
        haystack = " ".join([symbol.name.replace("_", " "), str(symbol.path), symbol.source]).lower()
        score = sum(4 if term in symbol.name.lower().replace("_", " ") else 0 for term in terms)
        score += sum(haystack.count(term) for term in terms)
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
    haystack = " ".join([symbol.name.replace("_", " "), str(symbol.path), symbol.source]).lower()
    return sum(1 for term in terms if term in haystack)


def _anchor_recall(query: str, text: str) -> float:
    terms = _terms(query)
    if not terms:
        return 1.0
    normalized = text.lower().replace("_", " ")
    hits = sum(1 for term in terms if term in normalized)
    return hits / len(terms)


def _symbol_excerpt(symbol: Symbol, query: str, max_lines: int = 8) -> str:
    lines = [line.rstrip() for line in symbol.source.splitlines() if line.strip()]
    evidence_lines = lines[1:] or lines
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

