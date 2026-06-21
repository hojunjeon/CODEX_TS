from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

from efts.compactor import compact_output
from efts.ab_test import run_ab_test
from efts.hook import compact_post_tool_use_payload, install_post_tool_use_hook
from efts.packer import ContextPacker
from efts.store import ContextStore


class EftsCoreTests(unittest.TestCase):
    def test_pytest_compactor_preserves_failure_anchors(self) -> None:
        raw = Path("benchmarks/fixtures/pytest_failure.txt").read_text(encoding="utf-8")
        result = compact_output(raw, command="python -m pytest -vv")
        self.assertEqual(result.strategy, "pytest")
        self.assertIn("test_", result.text)
        self.assertIn("assert", result.text)
        self.assertIn("cache hit false", result.text)
        self.assertIn("auth -> csrf -> handler -> response", result.text)
        self.assertGreater(result.saving_ratio, 0.75)

    def test_context_pack_preserves_related_expiration_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = ContextPacker(
                Path("benchmarks/fixtures/sample_repo"),
                ContextStore(Path(tmp) / "context.sqlite"),
            ).build_pack("reject expired token", token_budget=260)

        self.assertIn("TokenVerifier", pack.text)
        self.assertIn("accepts", pack.text)
        self.assertIn("expires_at > now", pack.text)
        self.assertIn("reject_expired_token", pack.text)
        self.assertGreaterEqual(pack.saving_ratio, 0.94)

    def test_ab_test_reports_quality_fact_coverage(self) -> None:
        metrics = run_ab_test(Path("benchmarks/fixtures"))

        self.assertIn("quality_fact_coverage", metrics)
        self.assertEqual(metrics["anchor_recall"], 1.0)
        self.assertEqual(metrics["quality_fact_coverage"], 1.0)

    def test_store_retrieves_exact_raw_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ContextStore(Path(tmp) / "context.sqlite")
            raw = "line one\nline two\n"
            capture = store.capture("Bash", raw, command="demo")
            self.assertEqual(store.get(capture.id).text, raw)
            self.assertEqual(store.get(capture.id).sha256, capture.sha256)

    def test_post_tool_use_returns_structured_redacted_envelope(self) -> None:
        raw = "\n".join(
            [
                "heartbeat ok" for _ in range(800)
            ]
            + [
                "ERROR request_id=req_123 failed",
                "token: fake-redact-me",
                "tests/test_api.py:42: AssertionError",
            ]
        )
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "python -m pytest -vv"},
            "tool_response": raw,
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = compact_post_tool_use_payload(payload, ContextStore(Path(tmp) / "context.sqlite"), threshold_bytes=100)
        self.assertIsNotNone(result)
        context = result["hookSpecificOutput"]["additionalContext"]
        self.assertIn("_efts_hook", context)
        self.assertIn("schema_version: 1", context)
        self.assertIn("capture_ref: ctx://capture/", context)
        self.assertIn("sha256:", context)
        self.assertIn("redaction_count:", context)
        self.assertNotIn("fake-redact-me", context)

    def test_install_hook_replaces_legacy_token_saver_hooks_and_preserves_other_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            hooks_dir = codex_home / "hooks"
            hooks_dir.mkdir()
            legacy_shim = hooks_dir / "codex-token-saver-post-tool-use.ps1"
            legacy_custom_shim = hooks_dir / "custom-codex-token-saver-post-tool-use.ps1"
            legacy_shim.write_text("old", encoding="utf-8")
            legacy_custom_shim.write_text("old", encoding="utf-8")
            hooks_json = codex_home / "hooks.json"
            (codex_home / "config.toml").write_text(
                "\n".join(
                    [
                        '[hooks.state]',
                        '',
                        "[hooks.state.'C:\\Users\\user\\.codex\\hooks.json:post_tool_use:0:0']",
                        'trusted_hash = "sha256:legacy"',
                        '',
                        "[hooks.state.'C:\\Users\\user\\.codex\\hooks.json:post_tool_use:1:0']",
                        'trusted_hash = "sha256:stale"',
                        '',
                        "[hooks.state.'C:\\Users\\user\\.codex\\hooks.json:pre_tool_use:0:0']",
                        'trusted_hash = "sha256:keep"',
                        '',
                    ]
                ),
                encoding="utf-8",
            )
            hooks_json.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "PostToolUse": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "powershell.exe -File old\\codex-token-saver-post-tool-use.ps1",
                                            "timeout": 30,
                                        }
                                    ]
                                },
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "powershell.exe -File old\\custom-codex-token-saver-post-tool-use.ps1",
                                            "timeout": 30,
                                        }
                                    ]
                                },
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "powershell.exe -File other.ps1",
                                            "timeout": 30,
                                        }
                                    ]
                                },
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            install_post_tool_use_hook(codex_home, Path(tmp) / "context.sqlite", efts_command='"C:\\efts.cmd"')
            data = json.loads(hooks_json.read_text(encoding="utf-8"))
            serialized = json.dumps(data)
            self.assertIn("efts-post-tool-use.ps1", serialized)
            self.assertIn("other.ps1", serialized)
            self.assertNotIn("old\\\\codex-token-saver-post-tool-use.ps1", serialized)
            self.assertNotIn("old\\\\custom-codex-token-saver-post-tool-use.ps1", serialized)
            self.assertEqual(serialized.count("efts-post-tool-use.ps1"), 1)
            self.assertFalse(legacy_shim.exists())
            self.assertFalse(legacy_custom_shim.exists())
            self.assertTrue(any((codex_home / "backups" / "efts-migration").iterdir()))
            config = (codex_home / "config.toml").read_text(encoding="utf-8")
            if tomllib is not None:
                tomllib.loads(config)
            self.assertNotIn("sha256:legacy", config)
            self.assertNotIn("sha256:stale", config)
            self.assertIn("sha256:keep", config)
            self.assertIn("[hooks.state.", config)


if __name__ == "__main__":
    unittest.main()
