"""Workflow state: stages, approvals, integrity hashes, execution graph and stage checks.

Everything here is stdlib-only. ``state.json`` is the single source of truth for a
workflow and is only ever written through this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intent_first import trace

STAGES = ("intent", "spec", "plan", "execution")
SCHEMA_VERSION = 3
NODE_STATUSES = ("pending", "in_progress", "complete", "failed", "blocked")

DIRNAME = ".intent-first"
ACTIVE_FILE = "active"
PROJECT_CONFIG = "config.json"
DEFAULT_PROJECT_CONFIG = {"block_code_before_plan": True, "strict_approval": False}

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class WorkflowError(Exception):
    """A user-facing error; the CLI prints the message and exits 1."""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_stage(name: str) -> str:
    """Accept a stage name or its 1-based number."""
    if name.isdigit() and 1 <= int(name) <= len(STAGES):
        return STAGES[int(name) - 1]
    if name in STAGES:
        return name
    raise WorkflowError(f"Unknown stage '{name}'. Valid: {', '.join(STAGES)} (or 1-{len(STAGES)})")


def validate_id(wid: str) -> str:
    if not _ID_RE.match(wid):
        raise WorkflowError(
            f"Invalid workflow ID '{wid}'. Use letters, digits, '.', '_' or '-' (max 64 chars)."
        )
    return wid


# ── Files ─────────────────────────────────────────────────────

def _default_mode() -> int:
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


def write_atomic(path: Path, text: str) -> None:
    """Replace a file atomically, keeping its permissions (new files get the usual umask-based mode)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else _default_mode()
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def set_readonly(path: Path, readonly: bool) -> None:
    if not path.exists():
        return
    mode = path.stat().st_mode
    if readonly:
        mode &= ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    else:
        mode |= stat.S_IWUSR
    os.chmod(path, mode)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── Project root & config ─────────────────────────────────────

def find_root(start: Path | None = None) -> Path:
    """Project root: $INTENT_FIRST_ROOT, else nearest ancestor with .intent-first/, else git top-level, else cwd."""
    env = os.environ.get("INTENT_FIRST_ROOT")
    if env:
        return Path(env).resolve()
    start = (start or Path.cwd()).resolve()
    for d in (start, *start.parents):
        if (d / DIRNAME).is_dir():
            return d
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start, capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        pass
    return start


def workflows_dir(root: Path) -> Path:
    return root / DIRNAME / "workflows"


def load_project_config(root: Path) -> dict[str, Any]:
    cfg = dict(DEFAULT_PROJECT_CONFIG)
    path = root / DIRNAME / PROJECT_CONFIG
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update(data)
        except ValueError:
            pass
    return cfg


def save_project_config(root: Path, cfg: dict[str, Any]) -> None:
    write_atomic(root / DIRNAME / PROJECT_CONFIG, json.dumps(cfg, indent=2) + "\n")


def user_config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "intent-first" / "config.json"


def load_user_config() -> dict[str, Any]:
    path = user_config_path()
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except ValueError:
            return {}
    return {}


def save_user_config(cfg: dict[str, Any]) -> None:
    write_atomic(user_config_path(), json.dumps(cfg, indent=2) + "\n")


def default_user_name() -> str:
    name = os.environ.get("INTENT_FIRST_USER") or load_user_config().get("name")
    if name:
        return str(name)
    try:
        out = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


def get_active(root: Path) -> str | None:
    path = root / DIRNAME / ACTIVE_FILE
    if path.is_file():
        wid = path.read_text(encoding="utf-8").strip()
        return wid or None
    return None


def set_active(root: Path, wid: str | None) -> None:
    path = root / DIRNAME / ACTIVE_FILE
    if wid:
        write_atomic(path, wid + "\n")
    elif path.exists():
        path.unlink()


def list_workflow_ids(root: Path) -> list[str]:
    wdir = workflows_dir(root)
    if not wdir.is_dir():
        return []
    ids = [p.name for p in wdir.iterdir() if (p / "state.json").is_file()]
    return sorted(ids, key=lambda s: (0, int(s), "") if s.isdigit() else (1, 0, s))


def next_numeric_id(root: Path) -> str:
    wdir = workflows_dir(root)
    nums = [int(p.name) for p in wdir.iterdir() if p.name.isdigit()] if wdir.is_dir() else []
    return str(max(nums, default=0) + 1)


# ── Execution graph ───────────────────────────────────────────

class Graph:
    """A small DAG of work nodes stored inside state.json."""

    def __init__(self, nodes: list[dict[str, Any]]):
        self.nodes = nodes

    def get(self, node_id: str) -> dict[str, Any]:
        for n in self.nodes:
            if n["id"] == node_id:
                return n
        known = ", ".join(n["id"] for n in self.nodes) or "(none)"
        raise WorkflowError(f"Unknown node '{node_id}'. Known nodes: {known}")

    def add(self, node_id: str, name: str, deps: list[str], covers: list[str]) -> None:
        validate_id(node_id)
        if any(n["id"] == node_id for n in self.nodes):
            raise WorkflowError(f"Node '{node_id}' already exists")
        self.nodes.append({
            "id": node_id, "name": name, "depends_on": list(dict.fromkeys(deps)), "covers": list(dict.fromkeys(covers)),
            "status": "pending", "started_at": None, "completed_at": None,
        })

    def remove(self, node_id: str) -> None:
        self.get(node_id)
        dependents = [n["id"] for n in self.nodes if node_id in n.get("depends_on", [])]
        if dependents:
            raise WorkflowError(f"Cannot remove '{node_id}': {', '.join(dependents)} depend on it")
        self.nodes[:] = [n for n in self.nodes if n["id"] != node_id]

    def set_status(self, node_id: str, status: str) -> None:
        if status not in NODE_STATUSES or status == "blocked":
            raise WorkflowError(f"Invalid status '{status}'. Valid: pending, in_progress, complete, failed")
        node = self.get(node_id)
        if status in ("in_progress", "complete"):
            unmet = [d for d in node.get("depends_on", []) if self._status(d) != "complete"]
            if unmet:
                raise WorkflowError(f"Node '{node_id}' is waiting on: {', '.join(unmet)}")
        if status == "in_progress":
            node["started_at"] = now()
        elif status == "complete":
            node["completed_at"] = now()
        elif status == "pending":
            node["started_at"] = node["completed_at"] = None
        node["status"] = status
        if status == "failed":
            self._propagate_blocked(node_id)
        elif status in ("pending", "complete"):
            self._unblock()

    def _status(self, node_id: str) -> str:
        for n in self.nodes:
            if n["id"] == node_id:
                return n.get("status", "pending")
        return "missing"

    def _propagate_blocked(self, failed_id: str) -> None:
        queue, seen = [failed_id], set()
        while queue:
            cur = queue.pop(0)
            for n in self.nodes:
                if cur in n.get("depends_on", []) and n["id"] not in seen:
                    seen.add(n["id"])
                    if n.get("status") in ("pending", "in_progress"):
                        n["status"] = "blocked"
                    queue.append(n["id"])

    def _unblock(self) -> None:
        """Blocked nodes return to pending once none of their ancestors has failed."""
        changed = True
        while changed:
            changed = False
            for n in self.nodes:
                if n.get("status") == "blocked" and not any(
                    self._status(d) in ("failed", "blocked") for d in n.get("depends_on", [])
                ):
                    n["status"] = "pending"
                    changed = True

    def ready(self) -> list[dict[str, Any]]:
        return [
            n for n in self.nodes
            if n.get("status") == "pending"
            and all(self._status(d) == "complete" for d in n.get("depends_on", []))
        ]

    def issues(self) -> list[str]:
        out: list[str] = []
        ids = {n["id"] for n in self.nodes}
        for n in self.nodes:
            for d in n.get("depends_on", []):
                if d not in ids:
                    out.append(f"node '{n['id']}' depends on unknown node '{d}'")
        if self.topological_order() is None:
            out.append("execution graph has a dependency cycle")
        return out

    def topological_order(self) -> list[str] | None:
        ids = {n["id"] for n in self.nodes}
        indeg = {n["id"]: len({d for d in n.get("depends_on", []) if d in ids}) for n in self.nodes}
        queue = [nid for nid, d in indeg.items() if d == 0]
        order: list[str] = []
        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for n in self.nodes:
                if nid in n.get("depends_on", []):
                    indeg[n["id"]] -= 1
                    if indeg[n["id"]] == 0:
                        queue.append(n["id"])
        return order if len(order) == len(self.nodes) else None

    def depth(self) -> dict[str, int]:
        nm = {n["id"]: n for n in self.nodes}
        memo: dict[str, int] = {}

        def visit(nid: str, trail: frozenset[str]) -> int:
            if nid in memo:
                return memo[nid]
            deps = [d for d in nm[nid].get("depends_on", []) if d in nm and d not in trail]
            memo[nid] = 0 if not deps else 1 + max(visit(d, trail | {nid}) for d in deps)
            return memo[nid]

        for nid in nm:
            visit(nid, frozenset())
        return memo

    def counts(self) -> dict[str, int]:
        out = {s: 0 for s in NODE_STATUSES}
        for n in self.nodes:
            out[n.get("status", "pending")] = out.get(n.get("status", "pending"), 0) + 1
        return out


# ── Workflow ──────────────────────────────────────────────────

class Workflow:
    def __init__(self, root: Path, wid: str, data: dict[str, Any]):
        self.root = root
        self.id = wid
        self.data = data

    # -- persistence --
    @property
    def dir(self) -> Path:
        return workflows_dir(self.root) / self.id

    @property
    def state_path(self) -> Path:
        return self.dir / "state.json"

    def stage_file(self, stage: str) -> Path:
        return self.dir / f"{stage}.md"

    @classmethod
    def load(cls, root: Path, wid: str) -> Workflow:
        validate_id(wid)
        path = workflows_dir(root) / wid / "state.json"
        if not path.is_file():
            raise WorkflowError(f"Workflow '{wid}' not found ({path.parent})")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise WorkflowError(f"{path} is not valid JSON: {exc}") from exc
        if data.get("schema_version") != SCHEMA_VERSION:
            raise WorkflowError(
                f"{path} uses schema {data.get('schema_version')!r}; run `intent-first migrate`"
            )
        return cls(root, wid, data)

    @classmethod
    def create(cls, root: Path, wid: str, templates: dict[str, str], parent: str | None = None) -> Workflow:
        validate_id(wid)
        wdir = workflows_dir(root) / wid
        if wdir.exists():
            raise WorkflowError(f"Workflow '{wid}' already exists")
        data = {
            "schema_version": SCHEMA_VERSION,
            "id": wid,
            "created_at": now(),
            "parent": parent,
            "children": [],
            "stages": {s: {"approved_by": None, "approved_at": None, "sha256": None, "forced": False} for s in STAGES},
            "graph": {"nodes": []},
            "log": [{"at": now(), "event": "created"}],
        }
        wf = cls(root, wid, data)
        wdir.mkdir(parents=True)
        for s in STAGES:
            write_atomic(wf.stage_file(s), templates[s].replace("{{id}}", wid))
        wf.save()
        return wf

    def save(self) -> None:
        write_atomic(self.state_path, json.dumps(self.data, indent=2, ensure_ascii=False) + "\n")

    def log(self, event: str, **fields: Any) -> None:
        self.data.setdefault("log", []).append({"at": now(), "event": event, **fields})

    # -- stages --
    @property
    def graph(self) -> Graph:
        return Graph(self.data.setdefault("graph", {"nodes": []}).setdefault("nodes", []))

    def approved(self, stage: str) -> bool:
        return bool(self.data["stages"][stage].get("approved_at"))

    def stage_status(self, stage: str) -> str:
        """approved | draft (open for writing) | pending (waiting on the previous stage)."""
        if self.approved(stage):
            return "approved"
        idx = STAGES.index(stage)
        return "draft" if idx == 0 or self.approved(STAGES[idx - 1]) else "pending"

    def current_stage(self) -> str | None:
        for s in STAGES:
            if not self.approved(s):
                return s
        return None

    def approve(self, stage: str, by: str, force: bool = False) -> list[str]:
        """Approve a stage. Returns the check issues (empty on a clean approval).

        Raises WorkflowError if the stage cannot be approved, or if it has issues and force is False.
        """
        status = self.stage_status(stage)
        if status == "approved":
            raise WorkflowError(f"{stage} is already approved")
        if status == "pending":
            prev = STAGES[STAGES.index(stage) - 1]
            raise WorkflowError(f"Approve {prev} before {stage}")
        path = self.stage_file(stage)
        if not path.is_file():
            raise WorkflowError(f"{path.name} is missing; restore it before approving")
        earlier = [i for i in self.integrity_issues() if i.split(".md", 1)[0] in STAGES[:STAGES.index(stage)]]
        issues = earlier + check_stage(self, stage)
        if issues and not force:
            raise WorkflowError(
                f"{stage} is not ready:\n" + "\n".join(f"  - {i}" for i in issues)
                + "\nFix these, or approve anyway with --force."
            )
        path = self.stage_file(stage)
        self.data["stages"][stage] = {
            "approved_by": by, "approved_at": now(),
            "sha256": sha256_file(path), "forced": bool(issues),
        }
        set_readonly(path, True)
        if stage == "plan":
            self.data["git_base"] = trace.git_head(self.root)  # the report diffs against this
        self.log("approved", stage=stage, by=by, forced=bool(issues))
        self.save()
        if stage == STAGES[-1]:
            self.write_report()
            if get_active(self.root) == self.id:
                set_active(self.root, None)
        return issues

    @property
    def report_path(self) -> Path:
        return self.dir / "report.md"

    def write_report(self) -> Path:
        write_atomic(self.report_path, trace.build_report(self))
        return self.report_path

    def reopen(self, stage: str, by: str) -> list[str]:
        """Reopen a stage and every later one. Returns the stages that were reopened."""
        reopened = []
        for s in STAGES[STAGES.index(stage):]:
            if self.approved(s):
                self.data["stages"][s] = {"approved_by": None, "approved_at": None, "sha256": None, "forced": False}
                set_readonly(self.stage_file(s), False)
                reopened.append(s)
        if not reopened:
            raise WorkflowError(f"{stage} is not approved; nothing to reopen")
        self.log("reopened", stages=reopened, by=by)
        self.save()
        return reopened

    def integrity_issues(self) -> list[str]:
        out = []
        for s in STAGES:
            st = self.data["stages"][s]
            if not st.get("approved_at"):
                continue
            path = self.stage_file(s)
            if not path.is_file():
                out.append(f"{s}.md is approved but missing")
            elif st.get("sha256") and sha256_file(path) != st["sha256"]:
                out.append(f"{s}.md changed after approval (sha256 mismatch)")
            elif os.name != "nt" and path.stat().st_mode & stat.S_IWUSR:
                out.append(f"{s}.md is approved but writable")
        return out

    def summary(self) -> dict[str, Any]:
        counts = self.graph.counts()
        return {
            "id": self.id,
            "active": get_active(self.root) == self.id,
            "current_stage": self.current_stage(),
            "parent": self.data.get("parent"),
            "children": self.data.get("children", []),
            "stages": {
                s: {
                    "status": self.stage_status(s),
                    "file": str(self.stage_file(s).relative_to(self.root)),
                    "approved_by": self.data["stages"][s].get("approved_by"),
                    "approved_at": self.data["stages"][s].get("approved_at"),
                }
                for s in STAGES
            },
            "graph": {"total": len(self.graph.nodes), **counts},
        }


# ── Stage checks ──────────────────────────────────────────────

# Headings each stage file must contain, and which of them must have content.
REQUIRED_SECTIONS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "intent": (("Goals",), ("Goals",)),
    "spec": (
        ("Summary", "Behaviour", "Interfaces", "Decisions", "Acceptance Criteria", "Open Questions"),
        ("Summary", "Behaviour", "Decisions", "Acceptance Criteria"),
    ),
    "plan": (("Approach", "Steps", "Verification", "Open Questions"), ("Approach", "Steps", "Verification")),
    "execution": (("Progress", "Deviations", "Results"), ("Progress", "Results")),
}

_NONE_RE = re.compile(r"^(?:[-*]\s*)?(?:none|n/?a|nothing)\.?$", re.I)
_DEFER_RE = re.compile(r"\b(TODO|TBD|FIXME|XXX)\b")
_UNCHECKED_RE = re.compile(r"^\s*[-*]\s+\[ \]", re.M)
APPROVED_DEFER = "[APPROVED-DEFER"

parse_sections = trace.parse_sections


def open_questions(body: str) -> list[str]:
    """Unresolved lines in an Open Questions section ('None' and checked items count as resolved)."""
    out = []
    for line in body.splitlines():
        s = line.strip()
        if not s or _NONE_RE.match(s) or re.match(r"^[-*]\s+\[[xX]\]", s) or s.startswith("~~"):
            continue
        out.append(s)
    return out


def _sections_issues(name: str, text: str, stage: str) -> list[str]:
    sections = trace.parse_sections(text)
    required, nonempty = REQUIRED_SECTIONS[stage]
    issues: list[str] = []
    for heading in required:
        body = trace.find_section(sections, heading)
        if body is None:
            issues.append(f"{name}: missing '## {heading}' section")
        elif heading in nonempty and not body:
            issues.append(f"{name}: '## {heading}' is empty")
    for q in open_questions(trace.find_section(sections, "Open Questions") or ""):
        issues.append(f"{name}: open question: {q[:120]}")
    if stage != "intent":
        for line in trace.FENCE_RE.sub("", trace.strip_comments(text)).splitlines():
            if _DEFER_RE.search(line) and APPROVED_DEFER not in line:
                issues.append(f"{name}: unresolved marker without [APPROVED-DEFER: <name> <date>]: {line.strip()[:120]}")
    return issues


def check_stage(wf: Workflow, stage: str) -> list[str]:
    """Issues that block approving a stage."""
    path = wf.stage_file(stage)
    if not path.is_file():
        return [f"{path.name} is missing"]
    text = path.read_text(encoding="utf-8")
    issues = _sections_issues(path.name, text, stage)
    goal_map, goal_issues = trace.goals(trace.read(wf.stage_file("intent")))

    if stage == "intent":
        issues += goal_issues
        if not goal_map and trace.section(text, "Goals"):
            issues.append("intent.md: number each goal as `- G1: ...` so the spec can trace to it")
        return issues

    ac_map, ac_issues = trace.criteria(trace.read(wf.stage_file("spec")))
    if stage == "spec":
        issues += ac_issues
        for aid, (gids, _) in ac_map.items():
            unknown = [g for g in gids if g not in goal_map]
            if unknown:
                issues.append(f"spec.md: {aid} refers to unknown goal(s) {', '.join(unknown)}")
        for gid in goal_map:
            if not any(gid in gids for gids, _ in ac_map.values()):
                issues.append(f"spec.md: goal {gid} has no acceptance criterion")
        return issues

    nodes = wf.graph.nodes
    if stage == "plan":
        issues += [f"plan: {i}" for i in wf.graph.issues()]
        if not nodes:
            issues.append("plan: the execution graph is empty (`intent-first graph add`)")
        for n in nodes:
            covers = n.get("covers", [])
            if not covers:
                issues.append(f"plan: node '{n['id']}' covers no acceptance criterion")
            unknown = [a for a in covers if a not in ac_map]
            if unknown:
                issues.append(f"plan: node '{n['id']}' covers unknown criteria {', '.join(unknown)}")
        for aid in ac_map:
            if not any(aid in n.get("covers", []) for n in nodes):
                issues.append(f"plan: {aid} is not covered by any graph node")
        verified = set(trace.AC_REF_RE.findall(trace.section(text, "Verification")))
        for aid in ac_map:
            if aid not in verified:
                issues.append(f"plan.md: '## Verification' does not say how {aid} is proven")
        steps = trace.step_ids(text)
        for n in nodes:
            if n["id"] not in steps:
                issues.append(f"plan.md: no `### {n['id']}` subsection under '## Steps'")
        for sid in steps:
            if sid not in {n["id"] for n in nodes}:
                issues.append(f"plan.md: step '### {sid}' has no graph node")
        return issues

    # execution
    body = trace.FENCE_RE.sub("", trace.strip_comments(text))
    unchecked = len(_UNCHECKED_RE.findall(body))
    if unchecked:
        issues.append(f"{path.name}: {unchecked} unchecked checklist item(s)")
    unfinished = [n["id"] for n in nodes if n.get("status") != "complete"]
    if unfinished:
        issues.append(f"execution graph: not complete: {', '.join(unfinished)}")
    res = trace.results(text)
    for aid in ac_map:
        status, line = res.get(aid, (None, ""))
        if status is None:
            issues.append(f"execution.md: no result for {aid} under '## Results' (`- {aid}: pass — evidence`)")
        elif status == "fail" and APPROVED_DEFER not in line:
            issues.append(f"execution.md: {aid} failed: {line[:120]}")
    return issues


def check_advice(wf: Workflow, stage: str) -> list[str]:
    """Non-blocking notes about stage roles."""
    if stage != "spec":
        return []
    paths = trace.source_paths_outside_interfaces(trace.read(wf.stage_file("spec")))
    if not paths:
        return []
    return [f"spec.md mentions source files ({', '.join(paths[:5])}). The spec says what and why; "
            "file-level detail belongs in the plan."]
