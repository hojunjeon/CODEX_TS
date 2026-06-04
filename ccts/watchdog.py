from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

from .ab_test import run_ab_test


@dataclass(frozen=True)
class Gate:
    name: str
    status: str
    evidence: str


@dataclass(frozen=True)
class WatchdogReport:
    gates: list[Gate]

    def to_markdown(self) -> str:
        lines = [
            "# CCTS Requirement Watchdog",
            "",
            "| Gate | Status | Evidence |",
            "|---|---|---|",
        ]
        for gate in self.gates:
            lines.append(f"| {gate.name} | {gate.status} | {gate.evidence} |")
        return "\n".join(lines) + "\n"


class RequirementWatchdog:
    """Headless requirement watcher for Codex release gates."""

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()

    def evaluate(self, metrics: dict | None = None, run_tests: bool = False) -> WatchdogReport:
        if metrics is None:
            metrics = run_ab_test(self.root / "benchmarks" / "fixtures")
        gates = [
            self._gate_research(),
            self._gate_codex_assets(),
            self._gate_watchdog_subagent(),
            self._gate_post_tool_use_hook(),
            self._gate_installers(),
            self._gate_windows_zip(),
            self._gate_ab(metrics),
            self._gate_runtime(metrics),
            self._gate_case_savings(metrics),
            self._gate_docs(),
        ]
        if run_tests:
            gates.append(self._gate_tests())
        return WatchdogReport(gates)

    def _gate_research(self) -> Gate:
        path = self.root / "docs" / "REPO_ANALYSIS.md"
        expected = [
            "caveman",
            "rtk",
            "code-review-graph",
            "context-mode",
            "claude-token-optimizer",
            "token-optimizer",
            "token-optimizer-mcp",
            "claude-context",
            "claude-token-efficient",
            "token-savior",
        ]
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        missing = [name for name in expected if name not in text]
        return Gate("10 repo analysis", "PASS" if not missing else "FAIL", str(path) if not missing else "missing " + ",".join(missing))

    def _gate_codex_assets(self) -> Gate:
        skill = self.root / "skill" / "custom-codex-token-saver" / "SKILL.md"
        text = skill.read_text(encoding="utf-8") if skill.exists() else ""
        ok = "Codex" in text and "ccts" in text and "AGENTS.md" in text and "requirement-watchdog.md" in text
        return Gate("Codex skill and AGENTS workflow", "PASS" if ok else "FAIL", str(skill))

    def _gate_watchdog_subagent(self) -> Gate:
        path = self.root / "skill" / "custom-codex-token-saver" / "agents" / "requirement-watchdog.md"
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        expected = [
            "ccts watchdog --run-tests --until-pass",
            "94%",
            "Anchor recall 100%",
        ]
        missing = [item for item in expected if item not in text]
        status = "PASS" if path.exists() and not missing else "FAIL"
        evidence = str(path) if status == "PASS" else "missing " + ",".join(missing)
        return Gate("requirement watchdog subagent", status, evidence)

    def _gate_post_tool_use_hook(self) -> Gate:
        files = [
            self.root / "ccts" / "hook.py",
            self.root / "tests" / "test_ccts_core.py",
        ]
        ok = all(path.exists() for path in files)
        return Gate("Codex PostToolUse hook", "PASS" if ok else "FAIL", ", ".join(str(path) for path in files))

    def _gate_installers(self) -> Gate:
        files = [self.root / "install.bat", self.root / "install.ps1"]
        ok = all(path.exists() for path in files)
        return Gate("one-click Windows installer", "PASS" if ok else "FAIL", ", ".join(str(path) for path in files))

    def _gate_windows_zip(self) -> Gate:
        path = self.root / "dist" / "custom-codex-token-saver-windows.zip"
        ok = path.exists() and path.stat().st_size > 0
        return Gate("portable Windows zip", "PASS" if ok else "FAIL", str(path))

    def _gate_ab(self, metrics: dict) -> Gate:
        required = 0.94
        ok = metrics["overall_saving_ratio"] >= required and metrics["anchor_recall"] >= 1.0
        evidence = (
            f"A/B saving={metrics['overall_saving_ratio']:.1%}>={required:.0%}, "
            f"recall={metrics['anchor_recall']:.0%}"
        )
        return Gate("A/B token saving without anchor loss", "PASS" if ok else "FAIL", evidence)

    def _gate_runtime(self, metrics: dict) -> Gate:
        max_ms = 1000
        elapsed = float(metrics.get("elapsed_ms", max_ms + 1))
        ok = elapsed <= max_ms
        evidence = f"elapsed={elapsed:.3f}ms<=1000ms"
        return Gate("A/B benchmark runtime", "PASS" if ok else "FAIL", evidence)

    def _gate_case_savings(self, metrics: dict) -> Gate:
        floors = {
            "git_status_verbose": 0.50,
            "pytest_failure": 0.85,
            "symbol-pack": 0.95,
        }
        cases = {case["name"]: case for case in metrics["cases"]}
        failures: list[str] = []
        evidence_parts: list[str] = []
        for name, floor in floors.items():
            saving = cases.get(name, {}).get("saving_ratio", 0.0)
            evidence_parts.append(f"{name}={saving:.1%}>={floor:.0%}")
            if saving < floor:
                failures.append(name)
        status = "PASS" if not failures else "FAIL"
        evidence = "; ".join(evidence_parts)
        if failures:
            evidence += "; failing=" + ",".join(failures)
        return Gate("per-case Codex savings floors", status, evidence)

    def _gate_docs(self) -> Gate:
        docs = [self.root / "README.md", self.root / "docs" / "USAGE.md", self.root / "docs" / "AB_TEST_RESULTS.md"]
        ok = all(path.exists() for path in docs)
        return Gate("docs and benchmark report", "PASS" if ok else "FAIL", ", ".join(str(path) for path in docs))

    def _gate_tests(self) -> Gate:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
        )
        status = "PASS" if proc.returncode == 0 else "FAIL"
        evidence = "unittest discover rc=" + str(proc.returncode)
        return Gate("automated tests", status, evidence)

