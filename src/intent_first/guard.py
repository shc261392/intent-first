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
import shlex
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
HUMAN_ONLY_RE = re.compile(_CLI + r"(reopen|activate|deactivate|uninstall|config\s+set)\b")
APPROVE_RE = re.compile(_CLI + r"approve\b")
# Which arguments of a shell command it writes to: every operand, the last one, or all but the first.
WRITE_COMMANDS = {
    "rm": "all", "rmdir": "all", "mv": "all", "tee": "all", "touch": "all", "truncate": "all", "unlink": "all",
    "shred": "all", "cp": "last", "install": "last", "ln": "last", "rsync": "last", "chmod": "rest", "chown": "rest",
    "remove-item": "all", "move-item": "all", "set-content": "all", "add-content": "all", "out-file": "all",
    "new-item": "all", "clear-content": "all", "copy-item": "last",
}
COMMAND_PREFIXES = {"sudo", "env", "command", "exec", "nice", "nohup", "time"}
REDIRECTS = {">", ">>", ">|", "&>", "&>>"}
SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "|&"}
INTERPRETER_RE = re.compile(r"\b(?:python[0-9.]*|node|ruby|perl|php)\s+-[a-zA-Z]*[ceE]\b")
HEREDOC_RE = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)")
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
        if len(parts) <= 3 and parts[1:2] in ((), ("workflows",)):
            return "Workflow folders are kept or removed by the human (`intent-first uninstall --purge`); don't delete or move them."
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


def _strip_heredocs(cmd: str) -> str:
    """Drop here-document bodies so their text isn't parsed as commands."""
    out: list[str] = []
    end: str | None = None
    for line in cmd.splitlines():
        if end is not None:
            if line.strip() == end:
                end = None
            continue
        out.append(line)
        m = HEREDOC_RE.search(line)
        if m:
            end = m.group(1)
    return "\n".join(out)


def _operands(cmd: str, args: list[str]) -> list[str]:
    """The arguments a write command modifies."""
    if cmd == "dd":
        return [a[3:] for a in args if a.startswith("of=")]
    if cmd in ("sed", "perl"):
        if not any(a.startswith("-") and not a.startswith("--") and "i" in a or a.startswith("--in-place") for a in args):
            return []
        operands, script_given, skip = [], False, False
        for a in args:
            if skip:
                skip = False
            elif a in ("-e", "-E", "-f", "--expression", "--file"):
                script_given, skip = True, True
            elif not a.startswith("-"):
                operands.append(a)
        return operands if script_given else operands[1:]
    mode = WRITE_COMMANDS.get(cmd)
    operands = [a for a in args if not a.startswith("-")]
    if mode == "last":
        return operands[-1:] if len(operands) > 1 else []
    if mode == "rest":
        return operands[1:]
    return operands if mode == "all" else []


def shell_write_targets(cmd: str) -> list[str] | None:
    """Paths a shell command writes, removes or moves; None if it can't be parsed."""
    try:
        lexer = shlex.shlex(_strip_heredocs(cmd), posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return None
    targets: list[str] = []
    segment: list[str] = []
    for i, tok in enumerate(tokens + [";"]):
        if tok in REDIRECTS:
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("&"):
                targets.append(tokens[i + 1])
            if segment and segment[-1].isdigit():
                segment.pop()  # the fd in `2>file`
            continue
        if i > 0 and tokens[i - 1] in REDIRECTS | {"<", "<<", "<<<", ">&", "<&"}:
            continue  # the redirection's own target
        if tok in SEPARATORS:
            words = segment
            while words and (words[0].lower() in COMMAND_PREFIXES or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0])):
                words = words[1:]  # `sudo`, `env`, `VAR=value` before the command
            if words:
                name = words[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
                targets += _operands(name, words[1:])
            segment = []
        elif tok not in ("<", "<<", "<<<", ">&", "<&"):
            segment.append(tok)
    return [t for t in targets if t not in ("/dev/null", "-", "/dev/stdout", "/dev/stderr")]


def _glob_base(path: str) -> str:
    """For `dir/*.py` check `dir`: a glob writes somewhere inside its fixed prefix."""
    cut = min((path.find(c) for c in "*?[" if c in path), default=-1)
    return path if cut < 0 else (path[:cut].rsplit("/", 1)[0] if "/" in path[:cut] else ".")


def check_shell(project: Project, cmd: str, base: Path) -> str | None:
    m = HUMAN_ONLY_RE.search(cmd)
    if m:
        return f"`intent-first {m.group(1)}` is reserved for the human. Ask them to run it."
    if APPROVE_RE.search(cmd) and project.config().get("strict_approval"):
        return "strict_approval is on: only the human runs `intent-first approve`."
    targets = shell_write_targets(cmd)
    if targets is None or INTERPRETER_RE.search(cmd):
        # Can't see what an inline script or an unparsable command writes: protect the files it names.
        for wid, fname, owned in PROTECTED_IN_SHELL_RE.findall(cmd):
            if owned:
                return f".intent-first/{owned} is managed by the intent-first CLI; ask the human to change it."
            reason = _stage_rule(project.state(wid), wid, fname)
            if reason:
                return reason
        targets = targets or []
    for t in targets:
        p = Path(os.path.expanduser(_glob_base(t)))
        reason = check_write(project, p if p.is_absolute() else base / p)
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
            return check_shell(project, cmd, base)
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
