from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import sys
import time

from .compactor import compact_output
from .store import ContextStore


DEFAULT_THRESHOLD_BYTES = 12_000
DEFAULT_HOOK_TIMEOUT_SECONDS = 30
SECRET_KEY_RE = re.compile(r"authorization|token|secret|password|api[_-]?key|cookie|signature|private[_-]?key", re.I)
SECRET_VALUE_RES = [
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)\b(authorization|token|secret|password|api[_-]?key|cookie|signature|private[_-]?key)\s*[:=]\s*([^\s,;]+)"),
]


def compact_post_tool_use_payload(
    payload: dict,
    store: ContextStore,
    threshold_bytes: int = DEFAULT_THRESHOLD_BYTES,
) -> dict | None:
    event = payload.get("hook_event_name") or payload.get("hookEventName")
    if event != "PostToolUse":
        return None

    command = _command_from_payload(payload)
    raw = _raw_response_text(payload.get("tool_response"))
    original_bytes = len(raw.encode("utf-8", errors="replace"))
    if original_bytes < threshold_bytes or _is_capture_retrieval(command, payload):
        return None

    compact = compact_output(raw, command=command)
    capture = store.capture(str(payload.get("tool_name") or "PostToolUse"), raw, command=command)
    compact_text = _redact_context(compact.text)
    redaction_count = _redaction_count(raw)
    context = _preview_envelope(
        capture.id,
        capture.sha256,
        capture.bytes,
        compact.saving_ratio,
        compact.strategy,
        compact_text,
        redaction_count,
    )
    context_bytes = len(context.encode("utf-8", errors="replace"))
    if context_bytes >= original_bytes * 0.85:
        return None

    return {
        "continue": False,
        "stopReason": context,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        },
    }


def _preview_envelope(
    capture_id: int,
    sha256: str,
    byte_count: int,
    saving_ratio: float,
    strategy: str,
    compact_text: str,
    redaction_count: int,
) -> str:
    anchors = _extract_anchors(compact_text)
    retrieval_required = strategy in {"generic", "git-diff"} or saving_ratio < 0.5
    header = [
        "_efts_hook",
        "schema_version: 1",
        f"mode: captured",
        f"capture_ref: ctx://capture/{capture_id}",
        f"sha256: {sha256}",
        f"bytes: {byte_count}",
        f"strategy: {strategy}",
        f"saving: {saving_ratio:.1%}",
        f"fidelity: {'lossy' if retrieval_required else 'sufficient'}",
        f"retrieval_required: {str(retrieval_required).lower()}",
        f"redaction_count: {redaction_count}",
        f"anchors: {len(anchors)}",
        "--- preview ---",
        compact_text.strip(),
        "--- end_preview ---",
    ]
    if retrieval_required:
        header.append(f"Use efts get {capture_id} if exact omitted detail could affect the answer.")
    return "\n".join(header) + "\n"


def _extract_anchors(text: str) -> list[str]:
    anchors: list[str] = []
    for line in text.splitlines():
        if re.search(r"failed|error|assert|\.py:\d+|\.ts:\d+|\.rs:\d+|^M |^D |^A |^file |ctx://capture/", line, re.I):
            anchors.append(line.strip())
    return anchors[:40]


def _redaction_count(text: str) -> int:
    count = 0
    for pattern in SECRET_VALUE_RES:
        count += len(pattern.findall(text))
    return count


def install_post_tool_use_hook(
    codex_home: Path | str,
    db_path: Path | str,
    efts_command: str | None = None,
) -> Path:
    codex_home = Path(codex_home)
    hooks_dir = codex_home / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    shim = hooks_dir / "efts-post-tool-use.ps1"
    hooks_json = codex_home / "hooks.json"
    db_path = Path(db_path)
    stamp = int(time.time())

    command = efts_command or f'"{sys.executable}" -m efts'
    shim.write_text(_shim_script(command, db_path), encoding="utf-8")
    _archive_legacy_hook_shims(codex_home, hooks_dir, stamp)

    data = _read_hooks_json(hooks_json)
    hooks = data.setdefault("hooks", {})
    existing = hooks.setdefault("PostToolUse", [])
    existing = [
        entry
        for entry in existing
        if "efts-post-tool-use.ps1" not in json.dumps(entry)
        and "codex-token-saver-post-tool-use.ps1" not in json.dumps(entry)
        and "custom-codex-token-saver-post-tool-use.ps1" not in json.dumps(entry)
    ]
    hook_command = f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{shim}"'
    new_entry = {
        "hooks": [
            {
                "type": "command",
                "command": hook_command,
                "timeout": DEFAULT_HOOK_TIMEOUT_SECONDS,
                "statusMessage": "EFTS compacting large Codex output",
            }
        ]
    }
    hooks["PostToolUse"] = [new_entry, *existing]
    trust_rows = _trust_post_tool_use_hooks(data, hooks_json)

    if hooks_json.exists():
        backup = hooks_json.with_name(hooks_json.name + f".bak-efts-{stamp}")
        backup.write_text(hooks_json.read_text(encoding="utf-8"), encoding="utf-8")
    hooks_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _write_config_trust_state(codex_home / "config.toml", trust_rows, stamp)
    return shim


def _archive_legacy_hook_shims(codex_home: Path, hooks_dir: Path, stamp: int) -> None:
    backup_dir = codex_home / "backups" / "efts-migration"
    for name in ("codex-token-saver-post-tool-use.ps1", "custom-codex-token-saver-post-tool-use.ps1"):
        legacy = hooks_dir / name
        if not legacy.exists():
            continue
        backup_dir.mkdir(parents=True, exist_ok=True)
        destination = backup_dir / f"{stamp}-{name}"
        suffix = 1
        while destination.exists():
            destination = backup_dir / f"{stamp}-{suffix}-{name}"
            suffix += 1
        legacy.replace(destination)


def _raw_response_text(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def _command_from_payload(payload: dict) -> str:
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        return str(tool_input.get("command") or "")
    return ""


def _is_capture_retrieval(command: str, payload: dict) -> bool:
    haystack = " ".join([command, json.dumps(payload.get("tool_input", ""), ensure_ascii=False)]).lower()
    return "ctx://capture/" in haystack or " efts get " in f" {haystack} " or "efts get" in haystack


def _redact_context(text: str) -> str:
    redacted = text
    for pattern in SECRET_VALUE_RES:
        if pattern.pattern.startswith("(?i)\\b("):
            redacted = pattern.sub(lambda match: f"{match.group(1)}: [REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    lines: list[str] = []
    for line in redacted.splitlines():
        if SECRET_KEY_RE.search(line) and "[REDACTED]" not in line:
            key = line.split(":", 1)[0] if ":" in line else line.split("=", 1)[0]
            lines.append(f"{key}: [REDACTED]")
        else:
            lines.append(line)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def _read_hooks_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid hooks.json, refusing to overwrite: {path}: {exc}") from exc


def _trust_post_tool_use_hooks(data: dict, hooks_json: Path) -> list[dict[str, str]]:
    state = data.setdefault("state", {})
    rows: list[dict[str, str]] = []
    post_tool_use_entries = data.get("hooks", {}).get("PostToolUse", [])
    for group_index, entry in enumerate(post_tool_use_entries):
        for handler_index, hook in enumerate(entry.get("hooks", [])):
            if hook.get("type") != "command":
                continue
            if not _is_managed_post_tool_use_command(str(hook.get("command", ""))):
                continue
            identity = {
                "event_name": "post_tool_use",
                **({"matcher": entry["matcher"]} if "matcher" in entry else {}),
                "hooks": [
                    {
                        "type": "command",
                        "command": hook.get("command", ""),
                        "timeout": max(1, int(hook.get("timeout", 600))),
                        "async": False,
                        **({"statusMessage": hook["statusMessage"]} if hook.get("statusMessage") else {}),
                    }
                ],
            }
            trusted_hash = "sha256:" + hashlib.sha256(
                json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            key = f"{hooks_json}:post_tool_use:{group_index}:{handler_index}"
            state[key] = {"trusted_hash": trusted_hash}
            rows.append({"key": key, "trusted_hash": trusted_hash})
    return rows


def _is_managed_post_tool_use_command(command: str) -> bool:
    return "efts-post-tool-use.ps1" in command or "omx-native-hook-windows-shim.ps1" in command


def _write_config_trust_state(config_toml: Path, rows: list[dict[str, str]], stamp: int) -> None:
    if not rows:
        return
    config_toml.parent.mkdir(parents=True, exist_ok=True)
    if config_toml.exists():
        backup = config_toml.with_name(config_toml.name + f".bak-efts-trust-{stamp}")
        backup.write_text(config_toml.read_text(encoding="utf-8"), encoding="utf-8")
        text = config_toml.read_text(encoding="utf-8-sig")
    else:
        text = ""

    text = _remove_post_tool_use_trust_sections(text)
    for row in rows:
        section = f'[hooks.state."{_toml_escape_key(row["key"])}"]'
        block = f'{section}\ntrusted_hash = "{row["trusted_hash"]}"'
        pattern = re.escape(section) + r'\s*\r?\ntrusted_hash = "[^"]+"'
        if re.search(pattern, text):
            text = re.sub(pattern, block, text, count=1)
        else:
            if text and not text.endswith(("\n", "\r")):
                text += "\n"
            text += f"\n{block}\n"
    config_toml.write_text(text, encoding="utf-8")


def _remove_post_tool_use_trust_sections(text: str) -> str:
    pattern = re.compile(
        r"""
        ^[ \t]*\[hooks\.state\.
        (?:
            '[^'\r\n]*:post_tool_use:\d+:\d+'
            |
            "(?:\\.|[^"\r\n])*:post_tool_use:\d+:\d+"
        )
        \][ \t]*\r?\n
        [ \t]*trusted_hash[ \t]*=[ \t]*"[^"]*"[ \t]*(?:\r?\n)?
        """,
        re.MULTILINE | re.DOTALL | re.VERBOSE,
    )
    return pattern.sub("", text)


def _toml_escape_key(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _shim_script(efts_command: str, db_path: Path) -> str:
    quoted_db = str(db_path).replace("'", "''")
    return f"""$ErrorActionPreference = 'Stop'
$stdinPayload = [Console]::In.ReadToEnd()
$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = 'cmd.exe'
$startInfo.UseShellExecute = $false
$startInfo.RedirectStandardInput = $true
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
$startInfo.Arguments = '/c {efts_command} hook post-tool-use --db "{quoted_db}"'
$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $startInfo
$null = $process.Start()
$stdoutTask = $process.StandardOutput.ReadToEndAsync()
$stderrTask = $process.StandardError.ReadToEndAsync()
$process.StandardInput.Write($stdinPayload)
$process.StandardInput.Close()
$process.WaitForExit()
[Console]::Out.Write($stdoutTask.Result)
[Console]::Error.Write($stderrTask.Result)
exit $process.ExitCode
"""

