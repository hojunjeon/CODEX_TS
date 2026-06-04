from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .ab_test import run_ab_test, write_json, write_markdown
from .compactor import compact_output
from .hook import DEFAULT_THRESHOLD_BYTES, compact_post_tool_use_payload, install_post_tool_use_hook
from .packer import ContextPacker
from .scanner import scan_waste
from .store import ContextStore
from .watchdog import RequirementWatchdog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ccts", description="CCTS")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_filter = sub.add_parser("filter", help="compact stdin terminal output")
    p_filter.add_argument("--command", default="")
    p_filter.add_argument("--db", default=".custom-codex-token-saver/context.sqlite")
    p_filter.add_argument("--capture", action="store_true")

    p_capture = sub.add_parser("capture", help="store raw stdin/file in SQLite")
    p_capture.add_argument("--db", default=".custom-codex-token-saver/context.sqlite")
    p_capture.add_argument("--tool", default="Bash")
    p_capture.add_argument("--command", default="")
    p_capture.add_argument("file", nargs="?")

    p_get = sub.add_parser("get", help="retrieve ctx capture")
    p_get.add_argument("id", type=int)
    p_get.add_argument("--db", default=".custom-codex-token-saver/context.sqlite")
    p_get.add_argument("--preview", action="store_true")

    p_search = sub.add_parser("search", help="search captured raw evidence")
    p_search.add_argument("query")
    p_search.add_argument("--db", default=".custom-codex-token-saver/context.sqlite")

    p_pack = sub.add_parser("pack", help="build a query-focused Codex context pack")
    p_pack.add_argument("--root", default=".")
    p_pack.add_argument("--query", required=True)
    p_pack.add_argument("--budget", type=int, default=1200)
    p_pack.add_argument("--db", default=".custom-codex-token-saver/context.sqlite")

    p_scan = sub.add_parser("scan", help="find ghost-token risks")
    p_scan.add_argument("--root", default=".")

    p_ab = sub.add_parser("ab-test", help="run local A/B benchmark")
    p_ab.add_argument("--fixtures", default="benchmarks/fixtures")
    p_ab.add_argument("--json")
    p_ab.add_argument("--markdown")

    p_watch = sub.add_parser("watchdog", help="run requirement watchdog")
    p_watch.add_argument("--run-tests", action="store_true")
    p_watch.add_argument("--until-pass", action="store_true")
    p_watch.add_argument("--max-runs", type=int, default=3)
    p_watch.add_argument("--output")

    p_hook = sub.add_parser("hook", help="Codex hook helpers")
    hook_sub = p_hook.add_subparsers(dest="hook_cmd", required=True)
    p_post = hook_sub.add_parser("post-tool-use", help="compact Codex PostToolUse JSON from stdin")
    p_post.add_argument("--db", default=os.environ.get("CCTS_DB", ".custom-codex-token-saver/context.sqlite"))
    p_post.add_argument(
        "--threshold-bytes",
        type=int,
        default=int(os.environ.get("CCTS_HOOK_THRESHOLD", str(DEFAULT_THRESHOLD_BYTES))),
    )

    p_install_hook = sub.add_parser("install-hook", help="install Codex PostToolUse hook shim")
    p_install_hook.add_argument("--codex-home", default=os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    p_install_hook.add_argument("--db", default=os.environ.get("CCTS_DB", ".custom-codex-token-saver/context.sqlite"))
    p_install_hook.add_argument("--ccts-command")

    p_init = sub.add_parser("init", help="write Codex AGENTS.md instructions for this repo")
    p_init.add_argument("--root", default=".")
    p_init.add_argument("--force", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "filter":
        raw = sys.stdin.read()
        result = compact_output(raw, command=args.command)
        if args.capture:
            cap = ContextStore(Path(args.db)).capture("Bash", raw, command=args.command)
            sys.stdout.write(result.text)
            sys.stdout.write(f"\nraw=ctx://capture/{cap.id} sha256={cap.sha256}\n")
        else:
            sys.stdout.write(result.text)
        return 0

    if args.cmd == "capture":
        text = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
        cap = ContextStore(Path(args.db)).capture(args.tool, text, command=args.command)
        print(f"ctx://capture/{cap.id} bytes={cap.bytes} lines={cap.lines} sha256={cap.sha256}")
        return 0

    if args.cmd == "get":
        store = ContextStore(Path(args.db))
        print(store.preview(args.id) if args.preview else store.get(args.id).text, end="")
        return 0

    if args.cmd == "search":
        store = ContextStore(Path(args.db))
        for hit in store.search(args.query):
            print(f"ctx://capture/{hit.id} {hit.tool} {hit.command} bytes={hit.bytes} sha256={hit.sha256}")
        return 0

    if args.cmd == "pack":
        pack = ContextPacker(Path(args.root), ContextStore(Path(args.db))).build_pack(args.query, args.budget)
        print(pack.text, end="")
        print(f"\n[ccts] baseline={pack.baseline_tokens} optimized={pack.optimized_tokens} saving={pack.saving_ratio:.1%} recall={pack.anchor_recall:.0%}")
        return 0

    if args.cmd == "scan":
        findings = scan_waste(Path(args.root))
        for finding in findings:
            print(f"{finding.path}: ~{finding.estimated_tokens} tokens; {finding.reason}; {finding.recommendation}")
        return 0

    if args.cmd == "ab-test":
        metrics = run_ab_test(Path(args.fixtures))
        if args.json:
            write_json(metrics, Path(args.json))
        if args.markdown:
            write_markdown(metrics, Path(args.markdown))
        print(f"PASS A/B saving={metrics['overall_saving_ratio']:.1%} recall={metrics['anchor_recall']:.0%} elapsed={metrics['elapsed_ms']}ms")
        return 0

    if args.cmd == "watchdog":
        watcher = RequirementWatchdog(Path.cwd())
        report = None
        runs = max(1, args.max_runs if args.until_pass else 1)
        for _ in range(runs):
            report = watcher.evaluate(run_tests=args.run_tests)
            if all(gate.status == "PASS" for gate in report.gates):
                break
        assert report is not None
        text = report.to_markdown()
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(text, encoding="utf-8")
        print(text, end="")
        return 0 if all(gate.status == "PASS" for gate in report.gates) else 1

    if args.cmd == "hook" and args.hook_cmd == "post-tool-use":
        try:
            payload = json.loads(sys.stdin.read() or "{}")
            result = compact_post_tool_use_payload(
                payload,
                ContextStore(Path(args.db)),
                threshold_bytes=args.threshold_bytes,
            )
            if result is not None:
                print(json.dumps(result, ensure_ascii=False))
        except Exception as exc:
            try:
                Path(args.db).parent.mkdir(parents=True, exist_ok=True)
                log_path = Path(args.db).with_name("hook-errors.jsonl")
                with log_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n")
            except Exception:
                pass
        return 0

    if args.cmd == "install-hook":
        shim = install_post_tool_use_hook(Path(args.codex_home), Path(args.db), ccts_command=args.ccts_command)
        print("Installed CCTS PostToolUse hook:")
        print(f"  shim: {shim}")
        print(f"  db: {Path(args.db)}")
        print("Restart Codex Desktop sessions to guarantee hook reload.")
        return 0

    if args.cmd == "init":
        target = Path(args.root) / "AGENTS.md"
        if target.exists() and not args.force:
            print(f"AGENTS.md exists: {target}. Re-run with --force to overwrite.")
            return 2
        target.write_text(_agents_template(), encoding="utf-8")
        print(f"wrote {target}")
        return 0

    return 2


def _agents_template() -> str:
    return """# CCTS

Use `ccts pack --query "<task>"` before broad file reads. Use `ccts filter --capture --command "<cmd>"` for noisy terminal output. Keep final replies concise, but preserve exact file paths, errors, commands, and decisions. If compacted context is insufficient, retrieve exact raw evidence with `ccts get <id>` from the shown `ctx://capture/<id>` reference.
"""


if __name__ == "__main__":
    raise SystemExit(main())

