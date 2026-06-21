from __future__ import annotations

from pathlib import Path
import json
import time

from .compactor import compact_output, estimate_tokens
from .packer import ContextPacker
from .store import ContextStore


def run_ab_test(fixtures_dir: Path | str) -> dict:
    fixtures = Path(fixtures_dir)
    started = time.perf_counter()
    cases: list[dict] = []

    for fixture in sorted(fixtures.glob("*.txt")):
        raw = fixture.read_text(encoding="utf-8")
        command = _command_for_fixture(fixture.name)
        compact = compact_output(raw, command=command)
        cases.append(
            {
                "name": fixture.stem,
                "type": "terminal-output",
                "baseline_tokens": compact.original_tokens,
                "optimized_tokens": compact.optimized_tokens,
                "saving_ratio": round(compact.saving_ratio, 4),
                "anchor_recall": _terminal_anchor_recall(raw, compact.text),
                "quality_fact_coverage": _fact_coverage(raw, compact.text, _quality_facts_for_fixture(fixture.name)),
                "strategy": compact.strategy,
            }
        )

    sample_repo = fixtures / "sample_repo"
    if sample_repo.exists():
        store = ContextStore(fixtures / ".ab" / "ctx.sqlite")
        pack = ContextPacker(sample_repo, store).build_pack("reject expired token", token_budget=260)
        baseline_text = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in sorted(sample_repo.rglob("*"))
            if path.is_file()
        )
        cases.append(
            {
                "name": "symbol-pack",
                "type": "codex-context-pack",
                "baseline_tokens": pack.baseline_tokens,
                "optimized_tokens": pack.optimized_tokens,
                "saving_ratio": round(pack.saving_ratio, 4),
                "anchor_recall": pack.anchor_recall,
                "quality_fact_coverage": _fact_coverage(baseline_text, pack.text, _symbol_pack_quality_facts()),
                "strategy": "sqlite-symbol-pack",
            }
        )

    baseline = sum(case["baseline_tokens"] for case in cases)
    optimized = sum(case["optimized_tokens"] for case in cases)
    saving = 0.0 if baseline == 0 else 1.0 - optimized / baseline
    recall = min((case["anchor_recall"] for case in cases), default=1.0)
    quality = min((case["quality_fact_coverage"] for case in cases), default=1.0)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "overall_baseline_tokens": baseline,
        "overall_optimized_tokens": optimized,
        "overall_saving_ratio": round(saving, 4),
        "anchor_recall": round(recall, 4),
        "quality_fact_coverage": round(quality, 4),
        "elapsed_ms": round(elapsed_ms, 3),
        "cases": cases,
    }


def write_json(metrics: dict, path: Path | str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")


def write_markdown(metrics: dict, path: Path | str) -> None:
    rows = [
        "| Case | Type | Baseline | Optimized | Saving | Recall | Quality |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for case in metrics["cases"]:
        rows.append(
            f"| {case['name']} | {case['type']} | {case['baseline_tokens']} | "
            f"{case['optimized_tokens']} | {case['saving_ratio']:.1%} | {case['anchor_recall']:.0%} | "
            f"{case['quality_fact_coverage']:.0%} |"
        )
    body = "\n".join(
        [
            "# EFTS A/B Test Results",
            "",
            "Baseline sends raw terminal/file context. Optimized sends compact facts plus SQLite `ctx://` references.",
            "",
            f"- Overall baseline tokens: {metrics['overall_baseline_tokens']}",
            f"- Overall optimized tokens: {metrics['overall_optimized_tokens']}",
            f"- Overall saving: {metrics['overall_saving_ratio']:.1%}",
            f"- Anchor recall: {metrics['anchor_recall']:.0%}",
            f"- Quality fact coverage: {metrics['quality_fact_coverage']:.0%}",
            f"- Runtime: {metrics['elapsed_ms']} ms",
            "",
            *rows,
            "",
        ]
    )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(body, encoding="utf-8")


def _command_for_fixture(name: str) -> str:
    lower = name.lower()
    if "pytest" in lower:
        return "python -m pytest -vv"
    if "git_status" in lower or "status" in lower:
        return "git status"
    if "rg" in lower:
        return "rg expired"
    if "log" in lower:
        return "tail app.log"
    return ""


def _terminal_anchor_recall(raw: str, compact: str) -> float:
    anchors: list[tuple[str, str | None]] = []
    for line in raw.splitlines():
        clean = line.replace("E       ", "").strip()
        if not clean:
            continue
        if clean.startswith("modified:"):
            path = clean.removeprefix("modified:").strip()
            anchors.append((clean, "M " + path))
        elif _search_anchor(clean):
            anchors.append((clean, _search_anchor(clean)))
        elif "failed" in clean.lower() and " passed " in clean.lower():
            anchors.append((clean, _compact_summary_anchor(clean)))
        elif clean.startswith("FAILED ") or "AssertionError" in clean or "assert " in clean or clean.startswith("ERROR "):
            anchors.append((clean, None))
    if not anchors:
        return 1.0
    compact_l = compact.lower()
    hits = 0
    for anchor, alternate in anchors:
        if anchor.lower() in compact_l or (alternate is not None and _alternate_anchor_hit(alternate, compact)):
            hits += 1
    return hits / len(anchors)


def _quality_facts_for_fixture(name: str) -> list[tuple[str, list[str]]]:
    lower = name.lower()
    if "pytest" in lower:
        return [
            ("failing test name", ["test_rejects_expired_token"]),
            ("failure location", ["tests/test_auth.py:42"]),
            ("actual/expected status", ["assert 200 == 401"]),
            ("cache state", ["cache hit false"]),
            ("auth middleware", ["middleware stack auth", "auth ->"]),
            ("csrf middleware", ["middleware stack csrf", "-> csrf"]),
            ("handler reached", ["middleware stack handler", "-> handler"]),
        ]
    if "git_status" in lower or "status" in lower:
        return [
            ("branch", ["feature/codex-token-saver"]),
            ("ahead count", ["ahead+2", "ahead of"]),
            ("modified compactor", ["codex_token_saver/compactor.py"]),
            ("modified README", ["README.md"]),
            ("modified usage doc", ["docs/USAGE.md"]),
            ("untracked test", ["tests/test_compactor.py"]),
            ("untracked skill", ["skill/codex-token-saver/SKILL.md"]),
        ]
    return []


def _symbol_pack_quality_facts() -> list[tuple[str, list[str]]]:
    return [
        ("verifier class", ["TokenVerifier"]),
        ("token acceptance method", ["accepts"]),
        ("token expiration predicate", ["expires_at > now"]),
        ("target assertion helper", ["reject_expired_token"]),
    ]


def _fact_coverage(raw: str, compact: str, facts: list[tuple[str, list[str]]]) -> float:
    if not facts:
        return 1.0
    raw_l = raw.lower()
    compact_l = compact.lower()
    relevant = [needles for _label, needles in facts if any(needle.lower() in raw_l for needle in needles)]
    if not relevant:
        return 1.0
    hits = sum(1 for needles in relevant if any(needle.lower() in compact_l for needle in needles))
    return hits / len(relevant)


def _compact_summary_anchor(line: str) -> str | None:
    import re

    match = re.search(r"(\d+\s+failed.*?in\s+[0-9.]+s)", line.strip("= "), re.I)
    return match.group(1) if match else None


def _alternate_anchor_hit(alternate: str, compact: str) -> bool:
    import re

    compact_l = compact.lower()
    if alternate.lower() in compact_l:
        return True
    if alternate.startswith("search:"):
        _, path, line_no = alternate.split(":", 2)
        return re.search(rf"(?im)^{re.escape(path)}:\s+lines\s+[^;\n]*\b{re.escape(line_no)}\b", compact) is not None
    if " " not in alternate:
        return False
    status, path = alternate.split(" ", 1)
    return re.search(rf"(?im)^{re.escape(status)}\b.*{re.escape(path)}", compact) is not None


def _search_anchor(line: str) -> str | None:
    import re

    match = re.match(r"^(.+\.(?:py|ts|tsx|rs|go|js|jsx|java|cs|rb|php)):(\d+):", line)
    if not match:
        return None
    return f"search:{match.group(1)}:{match.group(2)}"

