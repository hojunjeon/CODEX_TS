from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ccts.compactor import compact_output
from ccts.hook import compact_post_tool_use_payload, install_post_tool_use_hook
from ccts.store import ContextStore


class CctsCoreTests(unittest.TestCase):
    def test_pytest_compactor_preserves_failure_anchors(self) -> None:
        raw = Path("benchmarks/fixtures/pytest_failure.txt").read_text(encoding="utf-8")
        result = compact_output(raw, command="python -m pytest -vv")
        self.assertEqual(result.strategy, "pytest")
        self.assertIn("test_", result.text)
        self.assertIn("assert", result.text)
        self.assertGreater(result.saving_ratio, 0.75)

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
                "Authorization: Bearer sk-secretsecretsecret",
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
        self.assertIn("_ccts_hook", context)
        self.assertIn("schema_version: 1", context)
        self.assertIn("capture_ref: ctx://capture/", context)
        self.assertIn("sha256:", context)
        self.assertIn("redaction_count:", context)
        self.assertNotIn("sk-secretsecretsecret", context)

    def test_install_hook_replaces_legacy_cts_hook_and_preserves_other_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            hooks_json = codex_home / "hooks.json"
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
            install_post_tool_use_hook(codex_home, Path(tmp) / "context.sqlite", ccts_command='"C:\\ccts.cmd"')
            data = json.loads(hooks_json.read_text(encoding="utf-8"))
            serialized = json.dumps(data)
            self.assertIn("custom-codex-token-saver-post-tool-use.ps1", serialized)
            self.assertIn("other.ps1", serialized)
            self.assertNotIn("old\\\\codex-token-saver-post-tool-use.ps1", serialized)
            self.assertEqual(serialized.count("custom-codex-token-saver-post-tool-use.ps1"), 1)
            config = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn("[hooks.state.", config)


if __name__ == "__main__":
    unittest.main()
