#!/usr/bin/env python3
"""Intent-First guard — one pre-tool-use hook for Claude Code, GitHub Copilot, Cursor, Codex and OpenCode.

Installed by `intent-first init` as `.intent-first/guard.py`. It reads the hook event
JSON on stdin and exits 2 with a reason to block the tool call, or 0 to allow it.

What it blocks (only while the project has Intent-First workflows):
  * edits to an approved stage file, to state.json, or to files the CLI owns;
  * writing a stage before the previous stage is approved;
  * edits outside .intent-first/ while the active workflow's plan is unapproved
    (disable with `intent-first config set block_code_before_plan false`);
  * agent shell commands that bypass the protocol (`intent-first reopen`, ...).

It is a seatbelt, not a sandbox: errors in the guard itself never block the agent.
Stdlib only, Python 3.9+, no imports from the intent_first package.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

STAGES = ("intent", "spec", "plan", "execution")
OWNED_FILES = ("guard.py", "config.json", "manifest.json", "active")
PATH_KEYS = (
    "file_path", "filePath", "path", "target_file", "targetFile", "notebook_path",
    "filename", "file", "destination", "new_path", "newPath", "old_path", "oldPath",
)
WRITE_HINTS = ("write", "edit", "create", "patch", "delete", "replace", "notebook", "move", "rename", "insert")
SHELL_HINTS = ("bash", "shell", "powershell", "terminal", "exec", "command")
PATCH_PATH_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+?)\s*$|^\*\*\* Move to: (.+?)\s*$", re.M)
# The CLI in command position: `intent-first`, a path to it, its .pyz, or `python -m intent_first`.
_CLI = r"(?:^|[\s;&|(/])intent[-_]first(?:\.pyz)?\s+"
HUMAN_ONLY_RE = re.compile(_CLI + r"(reopen|deactivate|uninstall|config\s+set)\b")
APPROVE_RE = re.compile(_CLI + r"approve\b")
SHELL_WRITE_RE = re.compile(
    r"(?<![0-9&])>>?|\btee\b|\bsed\s+-[a-zA-Z]*i|\bperl\s+-[a-zA-Z]*i|\brm\b|\bmv\b|\bchmod\b|\btruncate\b"
    r"|\bdd\b|\bpython[0-9.]*\s+-c\b|\bnode\s+-e\b|Set-Content|Out-File|Remove-Item|Move-Item"
)
PROTECTED_IN_SHELL_RE = re.compile(
    r"\.intent-first[/\\](?:workflows[/\\]([A-Za-z0-9._-]+)[/\\]([A-Za-z_]+\.(?:md|json))|(guard\.py|config\.json|manifest\.json|active)\b)"
)


# ── Event parsing ─────────────────────────────────────────────

def parse_event(data: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
    """Normalise the different hook payloads to (tool_name, tool_args, cwd)."""
    tool = str(data.get("tool_name") or data.get("toolName") or data.get("tool") or "")
    args: Any = data.get("tool_input", data.get("toolArgs", data.get("args", {})))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {"command": args}
    if not isinstance(args, dict):
        args = {}
    if not tool and isinstance(data.get("command"), str):  # Cursor beforeShellExecution
        tool, args = "shell", {"command": data["command"]}
    return tool, args, str(data.get("cwd") or os.getcwd())


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _paths(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if k in PATH_KEYS and isinstance(v, str):
                out.append(v)
            elif isinstance(v, (dict, list)):
                out += _paths(v)
    elif isinstance(value, list):
        for v in value:
            out += _paths(v)
    return out


def patch_paths(args: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for s in _strings(args):
        if "*** Begin Patch" in s:
            out += [a or b for a, b in PATCH_PATH_RE.findall(s)]
    return out


def shell_command(args: dict[str, Any]) -> str:
    cmd = args.get("command", args.get("cmd", ""))
    if isinstance(cmd, list):
        cmd = " ".join(str(c) for c in cmd)
    return cmd if isinstance(cmd, str) else ""


# ── Project state ─────────────────────────────────────────────

class Project:
    def __init__(self, root: Path):
        self.root = root
        self.base = root / ".intent-first"

    def state(self, wid: str) -> dict[str, Any] | None:
        try:
            return json.loads((self.base / "workflows" / wid / "state.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def config(self) -> dict[str, Any]:
        cfg = {"block_code_before_plan": True, "strict_approval": False}
        try:
            data = json.loads((self.base / "config.json").read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update(data)
        except (OSError, ValueError):
            pass
        return cfg

    def active(self) -> str | None:
        try:
            return (self.base / "active").read_text(encoding="utf-8").strip() or None
        except OSError:
            return None


def _approved(state: dict[str, Any], stage: str) -> bool:
    return bool(state.get("stages", {}).get(stage, {}).get("approved_at"))


def _stage_rule(state: dict[str, Any] | None, wid: str, fname: str) -> str | None:
    if fname == "state.json":
        return (f"workflows/{wid}/state.json is managed by the intent-first CLI. "
                f"Use `intent-first approve|graph|status` instead of editing it.")
    if fname == "report.md":
        return f"workflows/{wid}/report.md is generated by `intent-first report {wid}`; don't edit it by hand."
    stage = fname[:-3] if fname.endswith(".md") else ""
    if not state or stage not in STAGES:
        return None
    if _approved(state, stage):
        return (f"{stage}.md of workflow '{wid}' is approved and locked. "
                f"Ask the human to run `intent-first reopen {wid} {stage}`, or start a new workflow.")
    idx = STAGES.index(stage)
    if idx > 0 and not _approved(state, STAGES[idx - 1]):
        prev = STAGES[idx - 1]
        return (f"{stage}.md of workflow '{wid}' waits for {prev} approval. "
                f"Finish {prev}.md and get the human's approval first.")
    return None


def check_write(project: Project, target: Path) -> str | None:
    try:
        rel = target.resolve().relative_to(project.root.resolve())
    except ValueError:
        return None  # outside the project
    parts = rel.parts
    if parts and parts[0] == ".intent-first":
        if len(parts) >= 4 and parts[1] == "workflows":
            return _stage_rule(project.state(parts[2]), parts[2], parts[3])
        if len(parts) == 2 and parts[1] in OWNED_FILES:
            return f".intent-first/{parts[1]} is managed by the intent-first CLI; ask the human to change it."
        return None
    wid = project.active()
    if not wid or not project.config().get("block_code_before_plan", True):
        return None
    state = project.state(wid)
    if state and not _approved(state, "plan"):
        stage = next((s for s in STAGES if not _approved(state, s)), "plan")
        return (f"Workflow '{wid}' is active and in its {stage} stage: project files stay unchanged "
                f"until the plan is approved. Continue the {stage} stage, or ask the human to run "
                f"`intent-first deactivate` for an unrelated change.")
    return None


def check_shell(project: Project, cmd: str) -> str | None:
    m = HUMAN_ONLY_RE.search(cmd)
    if m:
        return f"`intent-first {m.group(1)}` is reserved for the human. Ask them to run it."
    if APPROVE_RE.search(cmd) and project.config().get("strict_approval"):
        return "strict_approval is on: only the human runs `intent-first approve`."
    if ".intent-first" in cmd and SHELL_WRITE_RE.search(cmd):
        for wid, fname, owned in PROTECTED_IN_SHELL_RE.findall(cmd):
            if owned:
                return f".intent-first/{owned} is managed by the intent-first CLI; ask the human to change it."
            reason = _stage_rule(project.state(wid), wid, fname)
            if reason:
                return reason
    return None


def decide(data: dict[str, Any], root: Path) -> str | None:
    """Return a reason to block, or None to allow."""
    project = Project(root)
    if not (project.base / "workflows").is_dir():
        return None
    tool, args, cwd = parse_event(data)
    name = tool.lower()
    base = Path(cwd)

    targets = patch_paths(args)
    if not targets:
        cmd = shell_command(args)
        if cmd and (not name or any(h in name for h in SHELL_HINTS)):
            return check_shell(project, cmd)
        if any(h in name for h in WRITE_HINTS):
            targets = _paths(args)
    for t in targets:
        p = Path(t)
        reason = check_write(project, p if p.is_absolute() else base / p)
        if reason:
            return reason
    return None


def _audit(root: Path, tool: str, reason: str) -> None:
    try:
        from datetime import datetime, timezone
        line = json.dumps({"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "event": "blocked", "tool": tool, "reason": reason})
        with open(root / ".intent-first" / "audit.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def main(root: Path | None = None) -> int:
    root = root or Path(os.environ.get("INTENT_FIRST_ROOT") or Path(__file__).resolve().parent.parent)
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        reason = decide(data, root) if isinstance(data, dict) else None
    except Exception:  # never let a guard bug block the agent
        return 0
    if not reason:
        return 0
    msg = f"[intent-first] {reason}"
    _audit(root, parse_event(data)[0], reason)
    # stderr + exit 2 is the block signal for Claude Code, Codex, Copilot and Cursor;
    # the JSON covers tools that read a decision object from stdout.
    print(json.dumps({"permission": "deny", "user_message": msg, "agent_message": msg,
                      "permissionDecision": "deny", "permissionDecisionReason": msg}))
    print(msg, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
