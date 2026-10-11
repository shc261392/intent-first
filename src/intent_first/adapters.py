"""Install Intent-First into a project for each supported agent, and remove it again.

Layout written into a project (everything is recorded in .intent-first/manifest.json):

  always    AGENTS.md block, .agents/skills/*, .intent-first/guard.py + config.json, .gitignore block
  claude    CLAUDE.md block, .claude/skills/*, PreToolUse hook in .claude/settings.json
  copilot   .github/hooks/intent-first.json
  cursor    hooks in .cursor/hooks.json
  codex     PreToolUse hook in .codex/hooks.json
  opencode  .opencode/plugins/intent-first.js, .opencode/commands/intent-*.md

`.agents/skills/` and AGENTS.md are read natively by Copilot, Cursor, Codex and OpenCode,
so the per-tool parts are only the hooks (and Claude Code's own skill/memory paths).
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
from importlib import resources
from pathlib import Path
from typing import Any, Callable

from intent_first import __version__
from intent_first.state import DEFAULT_PROJECT_CONFIG, DIRNAME, write_atomic

TOOLS = ("copilot", "claude", "cursor", "codex", "opencode")
TOOL_LABELS = {
    "copilot": "GitHub Copilot (VS Code, CLI, cloud agent)",
    "claude": "Claude Code",
    "cursor": "Cursor",
    "codex": "OpenAI Codex",
    "opencode": "OpenCode",
}
SKILLS = ("intent-first", "intent-spec", "intent-plan", "intent-execute", "intent-yolo")
GUARD_MARK = ".intent-first/guard.py"
MD_BEGIN, MD_END = "<!-- intent-first:begin -->", "<!-- intent-first:end -->"
GI_BEGIN, GI_END = "# intent-first:begin", "# intent-first:end"
GITIGNORE_BODY = ".intent-first/workflows/\n.intent-first/active\n.intent-first/audit.log\n"
MANIFEST = "manifest.json"

# POSIX shell entry point shared by every hook. It never blocks when the guard or
# Python is missing (a missing script would otherwise exit 2, which tools read as "deny").
GUARD_SH = (
    'G="${CLAUDE_PROJECT_DIR:-.}/.intent-first/guard.py"; '
    '[ -f "$G" ] || G="$(git rev-parse --show-toplevel 2>/dev/null)/.intent-first/guard.py"; '
    '[ -f "$G" ] || exit 0; P=python3; command -v "$P" >/dev/null 2>&1 || P=python; '
    'command -v "$P" >/dev/null 2>&1 || exit 0; exec "$P" "$G"'
)
GUARD_PS = (
    "if (Test-Path .intent-first/guard.py) { $input | python .intent-first/guard.py; exit $LASTEXITCODE }"
)
CLAUDE_MATCHER = "Write|Edit|MultiEdit|NotebookEdit|Bash"
CODEX_MATCHER = "apply_patch|Bash|shell|exec_command|Edit|Write"


def asset(rel: str) -> str:
    node = resources.files("intent_first").joinpath("assets")
    for part in rel.split("/"):
        node = node.joinpath(part)  # one part at a time: zipfile.Path.joinpath takes one argument on Python 3.9
    return node.read_text(encoding="utf-8")


def detect_tools(root: Path) -> list[str]:
    marks = {
        "copilot": (".github/copilot-instructions.md", ".github/prompts", ".github/agents",
                    ".github/skills", ".github/hooks", ".github/instructions", ".vscode"),
        "claude": ("CLAUDE.md", ".claude"),
        "cursor": (".cursor", ".cursorrules"),
        "codex": (".codex",),
        "opencode": (".opencode", "opencode.json", "opencode.jsonc"),
    }
    return [t for t in TOOLS if any((root / m).exists() for m in marks[t])]


# ── Manifest ──────────────────────────────────────────────────

class Manifest:
    """Tracks what init wrote so uninstall can remove exactly that."""

    def __init__(self, root: Path):
        self.root = root
        self.path = root / DIRNAME / MANIFEST
        data: dict[str, Any] = {}
        if self.path.is_file():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except ValueError:
                data = {}
        self.tools: list[str] = list(data.get("tools", []))
        self.files: set[str] = set(data.get("files", []))      # owned outright
        self.created: set[str] = set(data.get("created", []))  # shared files we created (delete if left empty)
        self.blocks: set[str] = set(data.get("blocks", []))    # marked text blocks
        self.json: set[str] = set(data.get("json", []))        # merged JSON hook entries

    def save(self) -> None:
        data = {
            "version": __version__, "tools": self.tools,
            "files": sorted(self.files), "created": sorted(self.created),
            "blocks": sorted(self.blocks), "json": sorted(self.json),
        }
        write_atomic(self.path, json.dumps(data, indent=2) + "\n")


# ── Primitives ────────────────────────────────────────────────

class Installer:
    def __init__(self, root: Path, report: Callable[[str], None] = lambda m: None):
        self.root = root
        self.m = Manifest(root)
        self.report = report
        self.touched: set[str] = set()
        self.warnings: list[str] = []

    def _rel(self, rel: str) -> Path:
        return self.root / rel

    def file(self, rel: str, content: str) -> None:
        path = self._rel(rel)
        if path.exists() and rel not in self.m.files and path.read_text(encoding="utf-8") != content:
            self.warnings.append(f"{rel} exists and was not created by intent-first; left unchanged")
            return
        write_atomic(path, content)
        self.m.files.add(rel)
        self.touched.add(rel)

    def block(self, rel: str, body: str, begin: str = MD_BEGIN, end: str = MD_END) -> None:
        path = self._rel(rel)
        block = f"{begin}\n{body.rstrip()}\n{end}\n"
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            text = _strip_block(text, begin, end)
            text = (text.rstrip() + "\n\n" if text.strip() else "") + block
        else:
            text = block
            self.m.created.add(rel)
        write_atomic(path, text)
        self.m.blocks.add(rel)
        self.touched.add(rel)

    def json_hook(self, rel: str, merge: Callable[[dict[str, Any]], None]) -> None:
        path = self._rel(rel)
        data: dict[str, Any] = {}
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8") or "{}")
            except ValueError:
                self.warnings.append(f"{rel} is not plain JSON; add the intent-first hook manually (see README)")
                return
            if not isinstance(data, dict):
                self.warnings.append(f"{rel} is not a JSON object; skipped")
                return
        else:
            self.m.created.add(rel)
        _unmerge(data)
        merge(data)
        write_atomic(path, json.dumps(data, indent=2) + "\n")
        self.m.json.add(rel)
        self.touched.add(rel)


def _strip_block(text: str, begin: str, end: str) -> str:
    start = text.find(begin)
    stop = text.find(end, start) if start >= 0 else -1
    if stop < 0:
        return text
    before = text[:start].rstrip("\n")
    after = text[stop + len(end):].lstrip("\n")
    if before and after:
        return before + "\n\n" + after
    rest = before or after
    return rest + "\n" if rest and not rest.endswith("\n") else rest


def _has_guard(value: Any) -> bool:
    return GUARD_MARK in json.dumps(value)


def _unmerge(data: dict[str, Any]) -> None:
    """Remove intent-first hook entries from a hooks config, in place."""
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return
    for event in list(hooks):
        entries = hooks[event]
        if isinstance(entries, list):
            hooks[event] = [e for e in entries if not _has_guard(e)]
            if not hooks[event]:
                del hooks[event]
    if not hooks:
        del data["hooks"]


def _is_trivial(data: dict[str, Any]) -> bool:
    return not data or set(data) <= {"version"}


# ── Tool adapters ─────────────────────────────────────────────

def _skill_files() -> dict[str, str]:
    return {name: asset(f"skills/{name}/SKILL.md") for name in SKILLS}


def _install_common(ins: Installer) -> None:
    base = DIRNAME
    ins.file(f"{base}/guard.py", _guard_source())
    cfg = ins._rel(f"{base}/config.json")
    if not cfg.exists():
        write_atomic(cfg, json.dumps(DEFAULT_PROJECT_CONFIG, indent=2) + "\n")
    ins.m.files.add(f"{base}/config.json")
    for name, text in _skill_files().items():
        ins.file(f".agents/skills/{name}/SKILL.md", text)
    ins.block("AGENTS.md", asset("agents-block.md"))
    ins.block(".gitignore", GITIGNORE_BODY, GI_BEGIN, GI_END)


def _guard_source() -> str:
    return resources.files("intent_first").joinpath("guard.py").read_text(encoding="utf-8")


def _claude_style_hook(matcher: str) -> Callable[[dict[str, Any]], None]:
    def merge(data: dict[str, Any]) -> None:
        data.setdefault("hooks", {}).setdefault("PreToolUse", []).append(
            {"matcher": matcher, "hooks": [{"type": "command", "command": GUARD_SH, "timeout": 10}]}
        )
    return merge


def _install_claude(ins: Installer) -> None:
    for name, text in _skill_files().items():
        ins.file(f".claude/skills/{name}/SKILL.md", text)
    ins.block("CLAUDE.md", asset("agents-block.md"))
    ins.json_hook(".claude/settings.json", _claude_style_hook(CLAUDE_MATCHER))


def _install_copilot(ins: Installer) -> None:
    # PascalCase PreToolUse gives Claude-format payloads and matchers (Copilot CLI, cloud agent, VS Code).
    cfg = {"version": 1, "hooks": {"PreToolUse": [{
        "type": "command", "matcher": "Write|Edit|Bash",
        "bash": GUARD_SH, "powershell": GUARD_PS, "cwd": ".", "timeoutSec": 10,
    }]}}
    ins.file(".github/hooks/intent-first.json", json.dumps(cfg, indent=2) + "\n")


def _install_cursor(ins: Installer) -> None:
    def merge(data: dict[str, Any]) -> None:
        data.setdefault("version", 1)
        hooks = data.setdefault("hooks", {})
        hooks.setdefault("preToolUse", []).append({"command": GUARD_SH, "timeout": 10})
        hooks.setdefault("beforeShellExecution", []).append({"command": GUARD_SH, "timeout": 10})
    ins.json_hook(".cursor/hooks.json", merge)


def _install_codex(ins: Installer) -> None:
    ins.json_hook(".codex/hooks.json", _claude_style_hook(CODEX_MATCHER))


def _install_opencode(ins: Installer) -> None:
    ins.file(".opencode/plugins/intent-first.js", asset("opencode-plugin.js"))
    for name in SKILLS:
        if name == "intent-first":
            continue
        desc = name.split("-", 1)[1]
        ins.file(
            f".opencode/commands/{name}.md",
            f"---\ndescription: Intent-First {desc} stage for a workflow ID\n---\n"
            f"Load the `{name}` skill and follow it for workflow $ARGUMENTS.\n",
        )


INSTALLERS: dict[str, Callable[[Installer], None]] = {
    "claude": _install_claude,
    "copilot": _install_copilot,
    "cursor": _install_cursor,
    "codex": _install_codex,
    "opencode": _install_opencode,
}


def install(root: Path, tools: list[str]) -> Installer:
    """Install (or re-install) for the given tools. Files from tools no longer selected are removed."""
    ins = Installer(root)
    previous = Manifest(root)
    (root / DIRNAME / "workflows").mkdir(parents=True, exist_ok=True)
    _install_common(ins)
    for t in tools:
        INSTALLERS[t](ins)
    # Drop what an earlier install wrote but this one did not.
    stale = Manifest(root)
    stale.files = previous.files - ins.touched - {f"{DIRNAME}/config.json"}
    stale.blocks = previous.blocks - ins.touched
    stale.json = previous.json - ins.touched
    stale.created = previous.created
    _remove(root, stale)
    ins.m.files -= stale.files
    ins.m.blocks -= stale.blocks
    ins.m.json -= stale.json
    ins.m.created &= ins.m.blocks | ins.m.json
    ins.m.tools = list(tools)
    ins.m.save()
    return ins


def _prune_dirs(path: Path, root: Path) -> None:
    d = path.parent
    while d != root and root in d.parents:
        try:
            d.rmdir()
        except OSError:
            return
        d = d.parent


def _remove(root: Path, m: Manifest) -> list[str]:
    removed: list[str] = []
    for rel in sorted(m.files):
        p = root / rel
        if p.is_file():
            p.unlink()
            removed.append(rel)
            _prune_dirs(p, root)
    for rel in sorted(m.blocks):
        p = root / rel
        if not p.is_file():
            continue
        begin, end = (GI_BEGIN, GI_END) if p.name == ".gitignore" else (MD_BEGIN, MD_END)
        text = _strip_block(p.read_text(encoding="utf-8"), begin, end)
        if not text.strip() and rel in m.created:
            p.unlink()
            _prune_dirs(p, root)
        else:
            write_atomic(p, text)
        removed.append(rel)
    for rel in sorted(m.json):
        p = root / rel
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8") or "{}")
        except ValueError:
            continue
        if isinstance(data, dict):
            _unmerge(data)
            if _is_trivial(data) and rel in m.created:
                p.unlink()
                _prune_dirs(p, root)
            else:
                write_atomic(p, json.dumps(data, indent=2) + "\n")
            removed.append(rel)
    return removed


def uninstall(root: Path, purge: bool = False) -> list[str]:
    m = Manifest(root)
    removed = _remove(root, m)
    base = root / DIRNAME
    for name in (MANIFEST, "active", "config.json", "audit.log"):
        p = base / name
        if p.exists():
            p.unlink()
    if purge and base.exists():
        if sys.version_info >= (3, 12):
            shutil.rmtree(base, onexc=_force_remove)
        else:
            shutil.rmtree(base, onerror=_force_remove)
        removed.append(DIRNAME + "/")
    else:
        try:
            (base / "workflows").rmdir()
            base.rmdir()
        except OSError:
            pass
    return removed


def _force_remove(func: Callable[..., Any], path: str, _exc: Any) -> None:
    os.chmod(path, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
    func(path)


def installed_tools(root: Path) -> list[str] | None:
    m = Manifest(root)
    return m.tools if m.path.is_file() else None
