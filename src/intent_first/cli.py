"""intent-first command-line interface."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from intent_first import __version__, adapters
from intent_first.state import (
    DEFAULT_PROJECT_CONFIG,
    DIRNAME,
    STAGES,
    Workflow,
    WorkflowError,
    check_stage,
    default_user_name,
    find_root,
    get_active,
    list_workflow_ids,
    load_project_config,
    load_user_config,
    next_numeric_id,
    now,
    resolve_stage,
    save_project_config,
    save_user_config,
    set_active,
    set_readonly,
    sha256_file,
    validate_id,
    workflows_dir,
    write_atomic,
)

ICONS = {"approved": "✅", "draft": "📝", "pending": "⬜"}
NODE_ICONS = {"pending": "⬜", "in_progress": "⏳", "complete": "✅", "failed": "❌", "blocked": "🚫"}
STAGE_SKILL = {"intent": "intent-first", "spec": "intent-spec", "plan": "intent-plan",
               "execution": "intent-execute", "artifacts": "intent-artifacts"}


def out(msg: str = "") -> None:
    print(msg)


def templates() -> dict[str, str]:
    return {s: adapters.asset(f"templates/{s}.md") for s in STAGES}


def _root() -> Path:
    return find_root()


def _load(wid: str) -> Workflow:
    return Workflow.load(_root(), wid)


# ── init / uninstall / doctor ─────────────────────────────────

def _parse_tools(value: str) -> list[str]:
    if value == "all":
        return list(adapters.TOOLS)
    if value in ("", "none"):
        return []
    tools = [t.strip().lower() for t in value.split(",") if t.strip()]
    bad = [t for t in tools if t not in adapters.TOOLS]
    if bad:
        raise WorkflowError(f"Unknown tool(s): {', '.join(bad)}. Choose from: {', '.join(adapters.TOOLS)}, all")
    return tools


def _ask_tools() -> list[str]:
    out("Which coding agents do you use here? (comma-separated numbers, Enter = all)")
    for i, t in enumerate(adapters.TOOLS, 1):
        out(f"  {i}) {adapters.TOOL_LABELS[t]}")
    try:
        reply = input("> ").strip()
    except EOFError:
        reply = ""
    if not reply:
        return list(adapters.TOOLS)
    picked = []
    for part in reply.split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= len(adapters.TOOLS):
            picked.append(adapters.TOOLS[int(part) - 1])
        elif part in adapters.TOOLS:
            picked.append(part)
    return list(dict.fromkeys(picked))


def cmd_init(a: argparse.Namespace) -> int:
    root = _root()
    if a.tools is not None:
        tools = _parse_tools(a.tools)
    else:
        tools = adapters.installed_tools(root) or adapters.detect_tools(root)
        if not tools and sys.stdin.isatty():
            tools = _ask_tools()
    ins = adapters.install(root, tools)
    out(f"Intent-First {__version__} installed in {root}")
    out(f"  tools: {', '.join(tools) if tools else 'none (AGENTS.md + .agents/skills only, no hooks)'}")
    for rel in sorted(ins.touched):
        out(f"  ✓ {rel}")
    for w in ins.warnings:
        out(f"  ⚠ {w}")
    if not tools:
        out("  Tip: `intent-first init --tools copilot,claude,cursor,codex,opencode` adds enforcement hooks.")
    if "codex" in tools:
        out("  Codex: open /hooks once and trust the project hook so it runs.")
    out("")
    out("Next: commit these files, then run `intent-first new <name>` and ask your agent to use the intent-first skill.")
    return 0


def cmd_uninstall(a: argparse.Namespace) -> int:
    root = _root()
    if not a.yes and sys.stdin.isatty():
        what = "everything, including workflows" if a.purge else "installed files (workflows are kept)"
        try:
            if input(f"Remove Intent-First {what} from {root}? [y/N] ").strip().lower() not in ("y", "yes"):
                out("Aborted.")
                return 1
        except EOFError:
            return 1
    removed = adapters.uninstall(root, purge=a.purge)
    for rel in removed:
        out(f"  ✓ {rel}")
    if not a.purge and workflows_dir(root).is_dir():
        out(f"Workflows kept in {workflows_dir(root)} (use --purge to delete them).")
    out("Intent-First removed.")
    return 0


def cmd_doctor(_a: argparse.Namespace) -> int:
    root = _root()
    out(f"intent-first {__version__} · Python {sys.version.split()[0]} · root {root}")
    tools = adapters.installed_tools(root)
    if tools is None:
        out("  ✗ not initialised here — run `intent-first init`")
        return 1
    out(f"  tools: {', '.join(tools) or 'none'}")
    m = adapters.Manifest(root)
    problems = 0
    for rel in sorted(m.files | m.blocks | m.json):
        ok = (root / rel).exists()
        problems += not ok
        out(f"  {'✓' if ok else '✗ missing'} {rel}")
    from intent_first import guard
    probe = {"tool_name": "Bash", "tool_input": {"command": "intent-first reopen x spec"}, "cwd": str(root)}
    blocked = guard.decide(probe, root) is not None
    problems += not blocked
    out(f"  {'✓' if blocked else '✗'} guard blocks human-only commands")
    active = get_active(root)
    out(f"  active workflow: {active or 'none'}")
    return 1 if problems else 0


# ── workflows ─────────────────────────────────────────────────

def cmd_new(a: argparse.Namespace) -> int:
    root = _root()
    wid = validate_id(a.id) if a.id else next_numeric_id(root)
    if a.parent:
        parent = Workflow.load(root, a.parent)
    wf = Workflow.create(root, wid, templates(), parent=a.parent)
    if a.parent:
        parent.data.setdefault("children", []).append(wid)
        parent.log("spawned", child=wid)
        parent.save()
    if not a.no_activate:
        set_active(root, wid)
    out(f"Created workflow {wid} → {wf.dir.relative_to(root)}/")
    out(f"Next: write {wf.stage_file('intent').relative_to(root)} (Goal is required), "
        f"then `intent-first approve {wid} intent`.")
    return 0


def cmd_list(a: argparse.Namespace) -> int:
    root = _root()
    rows = [Workflow.load(root, wid).summary() for wid in list_workflow_ids(root)]
    if a.json:
        out(json.dumps(rows, indent=2))
        return 0
    if not rows:
        out("No workflows. Create one with `intent-first new [name]`.")
        return 0
    for r in rows:
        stage = r["current_stage"] or "done"
        bar = "".join(ICONS[r["stages"][s]["status"]] for s in STAGES)
        mark = " (active)" if r["active"] else ""
        out(f"{bar}  {r['id']}{mark} — {stage}")
    return 0


def cmd_status(a: argparse.Namespace) -> int:
    root = _root()
    wid = a.id or get_active(root)
    if not wid:
        return cmd_list(a)
    wf = Workflow.load(root, wid)
    s = wf.summary()
    if a.json:
        s["integrity_issues"] = wf.integrity_issues()
        out(json.dumps(s, indent=2))
        return 0
    out(f"Workflow {wid}{' (active)' if s['active'] else ''}" + (f" · parent {s['parent']}" if s["parent"] else ""))
    for st in STAGES:
        info = s["stages"][st]
        detail = info["status"]
        if info["approved_at"]:
            detail = f"approved by {info['approved_by']} at {info['approved_at']}"
        out(f"  {ICONS[info['status']]} {st:<10} {detail}")
    g = s["graph"]
    if g["total"]:
        out(f"  graph: {g['complete']}/{g['total']} complete"
            + (f", {g['failed']} failed" if g["failed"] else "")
            + (f", {g['blocked']} blocked" if g["blocked"] else ""))
    for issue in wf.integrity_issues():
        out(f"  ⚠ {issue}")
    cur = s["current_stage"]
    if cur == "intent":
        out(f"Next: fill in {s['stages']['intent']['file']} (Goal is required), then `intent-first approve {wid} intent`")
    elif cur:
        out(f"Next: ask your agent to run the {STAGE_SKILL[cur]} skill for {wid}")
    else:
        out("Done.")
    return 0


def cmd_check(a: argparse.Namespace) -> int:
    wf = _load(a.id)
    stage = resolve_stage(a.stage) if a.stage else (wf.current_stage() or "artifacts")
    issues = check_stage(wf, stage) + wf.integrity_issues()
    if not issues:
        out(f"✓ {a.id}/{stage}: no issues")
        return 0
    out(f"✗ {a.id}/{stage}: {len(issues)} issue(s)")
    for i in issues:
        out(f"  - {i}")
    return 1


def cmd_approve(a: argparse.Namespace) -> int:
    wf = _load(a.id)
    stage = resolve_stage(a.stage) if a.stage else wf.current_stage()
    if not stage:
        raise WorkflowError(f"Workflow {a.id} is already complete")
    by = a.by or default_user_name()
    if a.yolo:
        by += " (yolo)"
    issues = wf.approve(stage, by, force=a.force)
    out(f"✅ {a.id}/{stage} approved by {by} and locked")
    for i in issues:
        out(f"  ⚠ approved with --force despite: {i}")
    nxt = wf.current_stage()
    if nxt:
        out(f"Next: {STAGE_SKILL[nxt]} {a.id}")
    else:
        out("Workflow complete.")
    return 0


def cmd_reopen(a: argparse.Namespace) -> int:
    wf = _load(a.id)
    stages = wf.reopen(resolve_stage(a.stage), a.by or default_user_name())
    out(f"Reopened {a.id}: {', '.join(stages)}")
    return 0


def cmd_activate(a: argparse.Namespace) -> int:
    wf = _load(a.id)
    set_active(wf.root, wf.id)
    out(f"Active workflow: {wf.id}")
    return 0


def cmd_deactivate(_a: argparse.Namespace) -> int:
    set_active(_root(), None)
    out("No active workflow. Project files can be edited freely.")
    return 0


# ── graph ─────────────────────────────────────────────────────

def _graph_editable(wf: Workflow) -> None:
    if wf.approved("plan"):
        raise WorkflowError("The plan is approved; the graph's nodes are fixed. Only `graph set` is allowed.")


def cmd_graph(a: argparse.Namespace) -> int:
    wf = _load(a.id)
    g = wf.graph
    if a.graph_cmd == "add":
        _graph_editable(wf)
        deps = [d.strip() for d in (a.deps or "").split(",") if d.strip()]
        g.add(a.node, a.name or a.node, deps)
        issues = g.issues()
        if issues:
            g.nodes.pop()
            raise WorkflowError("; ".join(issues))
        wf.save()
        out(f"Added node {a.node}" + (f" (after {', '.join(deps)})" if deps else ""))
    elif a.graph_cmd == "rm":
        _graph_editable(wf)
        g.remove(a.node)
        wf.save()
        out(f"Removed node {a.node}")
    elif a.graph_cmd == "set":
        if not wf.approved("plan") or wf.approved("execution"):
            raise WorkflowError("Node status changes only during execution (plan approved, execution not yet).")
        g.set_status(a.node, a.status)
        wf.log("node", node=a.node, status=a.status)
        wf.save()
        out(f"{NODE_ICONS[a.status]} {a.node}: {a.status}")
        ready = [n["id"] for n in g.ready()]
        if ready:
            out(f"Ready: {', '.join(ready)}")
    elif a.graph_cmd == "ready":
        ready = g.ready()
        if a.json:
            out(json.dumps(ready, indent=2))
        elif ready:
            for n in ready:
                out(f"→ {n['id']}: {n.get('name', '')}")
        else:
            c = g.counts()
            out("All nodes complete." if g.nodes and c["complete"] == len(g.nodes) else "No nodes ready.")
    elif a.graph_cmd == "show":
        if a.json:
            out(json.dumps(g.nodes, indent=2))
            return 0
        if not g.nodes:
            out("(empty graph)")
            return 0
        depth = g.depth()
        order = g.topological_order() or [n["id"] for n in g.nodes]
        c = g.counts()
        out(f"Graph {wf.id}: {c['complete']}/{len(g.nodes)} complete")
        for nid in sorted(order, key=lambda i: (depth.get(i, 0), order.index(i))):
            n = g.get(nid)
            deps = ", ".join(n.get("depends_on", [])) or "—"
            out(f"  {'  ' * depth.get(nid, 0)}{NODE_ICONS.get(n.get('status', 'pending'), '?')} "
                f"{nid}: {n.get('name', '')}  [after: {deps}]")
        for issue in g.issues():
            out(f"  ⚠ {issue}")
    return 0


# ── config ────────────────────────────────────────────────────

PROJECT_KEYS = tuple(DEFAULT_PROJECT_CONFIG)


def cmd_config(a: argparse.Namespace) -> int:
    root = _root()
    if a.config_cmd == "get":
        merged: dict[str, Any] = {"name": default_user_name(), **load_project_config(root)}
        if a.key:
            if a.key not in merged:
                raise WorkflowError(f"Unknown key '{a.key}'. Keys: name, {', '.join(PROJECT_KEYS)}")
            out(str(merged[a.key]).lower() if isinstance(merged[a.key], bool) else str(merged[a.key]))
        else:
            for k, v in merged.items():
                out(f"{k} = {str(v).lower() if isinstance(v, bool) else v}")
        return 0
    key, value = a.key, a.value
    if key == "name":
        cfg = load_user_config()
        cfg["name"] = value
        save_user_config(cfg)
    elif key in PROJECT_KEYS:
        if value.lower() not in ("true", "false"):
            raise WorkflowError(f"{key} must be true or false")
        cfg = load_project_config(root)
        cfg[key] = value.lower() == "true"
        save_project_config(root, cfg)
    else:
        raise WorkflowError(f"Unknown key '{key}'. Keys: name, {', '.join(PROJECT_KEYS)}")
    out(f"{key} = {value}")
    return 0


# ── migrate (v2 → v3) ─────────────────────────────────────────

V2_FILES = {"s1_intent.md": "intent", "s2_spec.md": "spec", "s3_plan.md": "plan",
            "s4_execution.md": "execution", "s5_artifacts.md": "artifacts"}
V2_DONE = {"intent": {"locked"}, "spec": {"approved", "locked"}, "plan": {"approved", "locked"},
           "execution": {"complete", "locked"}, "artifacts": {"complete", "locked"}}
V2_PROMPT_DIRS = (".github/prompts", ".cursor/prompts", ".claude/prompts", ".windsurf/prompts", ".antigravity/prompts")
V2_AGENT_DIRS = (".github/agents", ".cursor/agents", ".claude/agents", ".windsurf/agents", ".antigravity/agents")
V2_PROMPTS = ("wf-spec.prompt.md", "wf-plan.prompt.md", "wf-execution.prompt.md", "wf-artifacts.prompt.md", "wf-yolo.prompt.md")
V2_RULE_FILES = (".github/copilot-instructions.md", ".cursor/rules/intent-first.md", "CLAUDE.md", ".windsurfrules",
                 ".aider.rules.md", ".clinerules", ".antigravity/rules/intent-first.md")
V2_ONELINER = "For the Intent-First Agentic Workflow, see `.intent-first/rules.md`."


def _v2_status(text: str) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    stages: dict[str, dict[str, str]] = {}
    top: dict[str, str] = {}
    cur: str | None = None
    for line in text.splitlines():
        m = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if m:
            top[m.group(1)] = m.group(2).split(" #")[0].strip().strip('"')
            cur = None
            continue
        m = re.match(r"^  ([a-z]+):\s*$", line)
        if m:
            cur = m.group(1)
            stages[cur] = {}
            continue
        m = re.match(r"^    ([a-z_]+):\s*(.*)$", line)
        if m and cur:
            stages[cur][m.group(1)] = m.group(2).split(" #")[0].strip().strip('"')
    return stages, top


def _migrate_workflow(root: Path, d: Path) -> str:
    old, top = _v2_status((d / "status.yml").read_text(encoding="utf-8"))
    for f in d.iterdir():
        set_readonly(f, False)
    for old_name, stage in V2_FILES.items():
        if (d / old_name).is_file():
            (d / old_name).replace(d / f"{stage}.md")
        elif not (d / f"{stage}.md").exists():
            write_atomic(d / f"{stage}.md", templates()[stage].replace("{{id}}", d.name))
    nodes: list[dict[str, Any]] = []
    gpath = d / "execution-graph.json"
    if gpath.is_file():
        try:
            g = json.loads(gpath.read_text(encoding="utf-8"))
            nodes = g.get("graph", g).get("nodes", [])
        except (ValueError, AttributeError):
            nodes = []
    children = [c.strip() for c in top.get("spawned_workflows", "").strip("[]").split(",") if c.strip()]
    wf = Workflow(root, d.name, {
        "schema_version": 3, "id": d.name, "created_at": None,
        "parent": top.get("parent_workflow") or None, "children": children,
        "stages": {s: {"approved_by": None, "approved_at": None, "sha256": None, "forced": False} for s in STAGES},
        "graph": {"nodes": [{
            "id": n["id"], "name": n.get("name", n["id"]), "depends_on": n.get("depends_on", []),
            "status": n.get("status", "pending") if n.get("status") in ("pending", "in_progress", "complete", "failed", "blocked") else "pending",
            "started_at": n.get("started_at") or None, "completed_at": n.get("completed_at") or None,
        } for n in nodes if isinstance(n, dict) and "id" in n]},
        "log": [],
    })
    approved = []
    for s in STAGES:
        info = old.get(s, {})
        if info.get("status") not in V2_DONE[s]:
            break  # approvals must be contiguous from intent
        wf.data["stages"][s] = {
            "approved_by": info.get("approved_by") or "unknown (migrated)",
            "approved_at": info.get("approved_at") or info.get("locked_at") or info.get("completed_at") or now(),
            "sha256": sha256_file(wf.stage_file(s)), "forced": False,
        }
        set_readonly(wf.stage_file(s), True)
        approved.append(s)
    wf.log("migrated", from_version=2, approved=approved)
    wf.save()
    (d / "status.yml").unlink()
    if gpath.is_file():
        gpath.unlink()
    return f"{d.name} ({len(approved)}/5 stages approved)"


def cmd_migrate(_a: argparse.Namespace) -> int:
    root = _root()
    wdir = workflows_dir(root)
    done = []
    if wdir.is_dir():
        for d in sorted(wdir.iterdir()):
            if (d / "status.yml").is_file() and not (d / "state.json").exists():
                done.append(_migrate_workflow(root, d))
    for w in done:
        out(f"  ✓ migrated workflow {w}")
    cleaned = []
    for pd in V2_PROMPT_DIRS:
        for name in V2_PROMPTS:
            p = root / pd / name
            if p.is_file() and not p.is_symlink():
                p.unlink()
                cleaned.append(f"{pd}/{name}")
    for ad in V2_AGENT_DIRS:
        p = root / ad / "wf-auditor.agents.md"
        if p.is_file() and not p.is_symlink():
            p.unlink()
            cleaned.append(f"{ad}/wf-auditor.agents.md")
    for rf in V2_RULE_FILES:
        p = root / rf
        if p.is_file() and V2_ONELINER in p.read_text(encoding="utf-8"):
            text = p.read_text(encoding="utf-8").replace(V2_ONELINER, "").strip()
            if text:
                write_atomic(p, text + "\n")
            else:
                p.unlink()
            cleaned.append(rf)
    for rel in (f"{DIRNAME}/rules.md", f"{DIRNAME}/templates"):
        p = root / rel
        if p.is_file():
            p.unlink()
            cleaned.append(rel)
        elif p.is_dir():
            shutil.rmtree(p)
            cleaned.append(rel + "/")
    for c in cleaned:
        out(f"  ✓ removed v2 file {c}")
    for pd in (*V2_PROMPT_DIRS, *V2_AGENT_DIRS):
        try:
            (root / pd).rmdir()
        except OSError:
            pass
    if not done and not cleaned:
        out("Nothing to migrate.")
    else:
        out("Migration done. Run `intent-first init` to install the v3 skills and hooks.")
    return 0


def cmd_guard(_a: argparse.Namespace) -> int:
    from intent_first import guard
    return guard.main(_root())


# ── parser ────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="intent-first",
        description="Intent → Spec → Plan → Execution → Artifacts, with human approval between stages.",
    )
    p.add_argument("--version", action="version", version=f"intent-first {__version__}")
    sub = p.add_subparsers(dest="cmd", metavar="<command>")

    def add(name: str, func: Any, help: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help, description=help)
        sp.set_defaults(func=func)
        return sp

    sp = add("init", cmd_init, "install skills, AGENTS.md and hooks into this project (re-run to update)")
    sp.add_argument("--tools", help=f"comma-separated: {','.join(adapters.TOOLS)}, or 'all' / 'none'")
    sp = add("uninstall", cmd_uninstall, "remove everything init installed")
    sp.add_argument("--purge", action="store_true", help="also delete .intent-first/ including workflows")
    sp.add_argument("-y", "--yes", action="store_true", help="don't ask for confirmation")
    add("doctor", cmd_doctor, "check the installation")

    sp = add("new", cmd_new, "create a workflow (auto-numbered if no ID) and make it active")
    sp.add_argument("id", nargs="?")
    sp.add_argument("--parent", help="link as a follow-up of this workflow")
    sp.add_argument("--no-activate", action="store_true")
    sp = add("list", cmd_list, "list workflows")
    sp.add_argument("--json", action="store_true")
    sp = add("status", cmd_status, "show a workflow's stages (default: the active one)")
    sp.add_argument("id", nargs="?")
    sp.add_argument("--json", action="store_true")
    sp = add("check", cmd_check, "check a stage file is ready for approval, and approved files are intact")
    sp.add_argument("id")
    sp.add_argument("stage", nargs="?")
    sp = add("approve", cmd_approve, "approve and lock a stage (default: the current one)")
    sp.add_argument("id")
    sp.add_argument("stage", nargs="?")
    sp.add_argument("--by", help="approver name (default: config name, then git user.name)")
    sp.add_argument("--force", action="store_true", help="approve even if `check` reports issues")
    sp.add_argument("--yolo", action="store_true", help="mark as approved on the user's behalf")
    sp = add("reopen", cmd_reopen, "unlock an approved stage and every stage after it (human only)")
    sp.add_argument("id")
    sp.add_argument("stage")
    sp.add_argument("--by")
    sp = add("activate", cmd_activate, "make a workflow the active one")
    sp.add_argument("id")
    add("deactivate", cmd_deactivate, "clear the active workflow (human only)")

    sp = add("graph", cmd_graph, "manage a workflow's execution graph")
    gsub = sp.add_subparsers(dest="graph_cmd", metavar="<action>", required=True)
    g = gsub.add_parser("add", help="add a node (plan stage)")
    g.add_argument("id")
    g.add_argument("node")
    g.add_argument("--name")
    g.add_argument("--deps", help="comma-separated node IDs this node depends on")
    g = gsub.add_parser("rm", help="remove a node (plan stage)")
    g.add_argument("id")
    g.add_argument("node")
    g = gsub.add_parser("set", help="set a node's status (execution stage)")
    g.add_argument("id")
    g.add_argument("node")
    g.add_argument("status", choices=["pending", "in_progress", "complete", "failed"])
    for name, help in (("show", "show the graph"), ("ready", "list nodes ready to start")):
        g = gsub.add_parser(name, help=help)
        g.add_argument("id")
        g.add_argument("--json", action="store_true")

    sp = add("config", cmd_config, "get or set: name, block_code_before_plan, strict_approval")
    csub = sp.add_subparsers(dest="config_cmd", metavar="<get|set>", required=True)
    c = csub.add_parser("get")
    c.add_argument("key", nargs="?")
    c = csub.add_parser("set")
    c.add_argument("key")
    c.add_argument("value")

    add("migrate", cmd_migrate, "convert v2 workflows and remove v2 prompt/rule files")
    add("guard", cmd_guard, "run the pre-tool-use hook on stdin (used by agent hooks)")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    a = parser.parse_args(argv)
    if not getattr(a, "func", None):
        parser.print_help()
        return 0
    try:
        return int(a.func(a) or 0)
    except WorkflowError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


def _entry() -> None:
    """Entry point for the zipapp, which ignores main()'s return value."""
    sys.exit(main())


if __name__ == "__main__":
    _entry()
