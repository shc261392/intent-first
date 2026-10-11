"""Markdown parsing and goal traceability.

Intent mapping is not a stage of its own: it is a thread of IDs through every stage.

    intent.md     - G1: goal                      (what must be true, and why)
    spec.md       - AC1 (G1): acceptance criterion (observable proof of a goal)
    plan          graph node --covers AC1, and a Verification line per AC
    execution.md  - AC1: pass — evidence

`check` verifies the thread at each gate, and `report` renders it at the end.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
FENCE_RE = re.compile(r"^(```|~~~).*?^\1", re.S | re.M)

GOAL_RE = re.compile(r"^\s*[-*]\s*(G\d+)\s*[:.)\-–—]\s*(\S.*)$")
AC_START_RE = re.compile(r"^\s*[-*]\s*(AC\d+)\b")
AC_RE = re.compile(r"^\s*[-*]\s*(AC\d+)\s*[(\[]\s*(G\d+(?:\s*,\s*G\d+)*)\s*[)\]]\s*[:.\-–—]?\s*(\S.*)$")
RESULT_RE = re.compile(r"^\s*[-*]\s*(AC\d+)\b[^\n]*?\b(pass(?:ed)?|fail(?:ed)?)\b", re.I)
AC_REF_RE = re.compile(r"\bAC\d+\b")
SOURCE_PATH_RE = re.compile(
    r"(?<![\w/])(?:[\w.-]+/)*[\w.-]+\.(?:py|ts|tsx|js|jsx|mjs|go|rs|java|kt|rb|php|cs|c|cc|cpp|h|hpp|swift|scala|vue|svelte)\b"
)


# ── Markdown sections ─────────────────────────────────────────

def strip_comments(text: str) -> str:
    return COMMENT_RE.sub("", text)


def parse_sections(text: str, level: int = 2) -> dict[str, str]:
    """Map lower-cased headings of the given level to their body, with HTML comments removed."""
    marker = "#" * level + " "
    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    in_fence = False
    for line in strip_comments(text).splitlines():
        if line.startswith(("```", "~~~")):
            in_fence = not in_fence
        if not in_fence and line.startswith(marker):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current, buf = line[len(marker):].strip().lower(), []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


def find_section(sections: dict[str, str], name: str) -> str | None:
    key = name.lower()
    for heading, body in sections.items():
        if heading == key or heading.startswith(key):
            return body
    return None


def section(text: str, name: str) -> str:
    return find_section(parse_sections(text), name) or ""


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


# ── The ID thread ─────────────────────────────────────────────

def goals(intent_text: str) -> tuple[dict[str, str], list[str]]:
    """Goal ID → text from intent.md's Goals section, plus format issues."""
    found: dict[str, str] = {}
    issues: list[str] = []
    for line in section(intent_text, "Goals").splitlines():
        if not line.strip():
            continue
        m = GOAL_RE.match(line)
        if m:
            if m.group(1) in found:
                issues.append(f"intent.md: duplicate goal {m.group(1)}")
            found[m.group(1)] = m.group(2).strip()
        elif re.match(r"^\s*[-*]\s", line):
            issues.append(f"intent.md: number each goal as `- G1: ...`: {line.strip()[:80]}")
    return found, issues


def criteria(spec_text: str) -> tuple[dict[str, tuple[list[str], str]], list[str]]:
    """AC ID → (goal IDs, text) from spec.md's Acceptance Criteria section, plus format issues."""
    found: dict[str, tuple[list[str], str]] = {}
    issues: list[str] = []
    for line in section(spec_text, "Acceptance Criteria").splitlines():
        if not AC_START_RE.match(line):
            continue
        m = AC_RE.match(line)
        if not m:
            issues.append(f"spec.md: write criteria as `- AC1 (G1): ...`: {line.strip()[:80]}")
            continue
        if m.group(1) in found:
            issues.append(f"spec.md: duplicate criterion {m.group(1)}")
        found[m.group(1)] = ([g.strip() for g in m.group(2).split(",")], m.group(3).strip())
    return found, issues


def results(execution_text: str) -> dict[str, tuple[str, str]]:
    """AC ID → ('pass' | 'fail', the full line) from execution.md's Results section."""
    out: dict[str, tuple[str, str]] = {}
    for line in section(execution_text, "Results").splitlines():
        m = RESULT_RE.match(line)
        if m:
            out[m.group(1)] = ("pass" if m.group(2).lower().startswith("pass") else "fail", line.strip())
    return out


def step_ids(plan_text: str) -> list[str]:
    """First word of each `###` heading inside the plan's Steps section."""
    out = []
    for heading in parse_sections(section(plan_text, "Steps"), level=3):
        word = heading.split()[0].strip("`*:") if heading.split() else ""
        if word:
            out.append(word)
    return out


def source_paths_outside_interfaces(spec_text: str) -> list[str]:
    """Source-file paths the spec mentions outside Interfaces and code fences (a sign of plan-level detail)."""
    found: list[str] = []
    for heading, body in parse_sections(spec_text).items():
        if heading.startswith("interfaces"):
            continue
        for path in SOURCE_PATH_RE.findall(FENCE_RE.sub("", body)):
            if path not in found:
                found.append(path)
    return found


# ── Report ────────────────────────────────────────────────────

def git_head(root: Path) -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


def git_diff_stat(root: Path, base: str) -> str:
    try:
        out = subprocess.run(
            ["git", "diff", "--stat", base, "--", ".", ":(exclude).intent-first"],
            cwd=root, capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.rstrip() if out.returncode == 0 else ""


def build_report(wf) -> str:  # wf: state.Workflow (untyped to avoid a circular import)
    from intent_first.state import STAGES

    intent_text = read(wf.stage_file("intent"))
    spec_text = read(wf.stage_file("spec"))
    exec_text = read(wf.stage_file("execution"))
    goal_map, _ = goals(intent_text)
    ac_map, _ = criteria(spec_text)
    res = results(exec_text)
    nodes = wf.graph.nodes

    title = next((ln[2:].strip() for ln in intent_text.splitlines() if ln.startswith("# ")), f"Workflow {wf.id}")
    title = re.sub(r"^Intent:\s*", "", title)
    icon = {"pass": "✅", "fail": "❌", None: "⬜"}

    lines = [f"# {title}", ""]
    approvals = []
    for s in STAGES:
        st = wf.data["stages"][s]
        if st.get("approved_at"):
            approvals.append(f"{s} ({st['approved_by']}, {st['approved_at'][:10]}{', forced' if st.get('forced') else ''})")
    lines += [f"Intent-First workflow `{wf.id}` · approved: {' → '.join(approvals) or 'none yet'}", ""]

    lines += ["## Outcome", "", "| Goal | Acceptance criteria | Result |", "|---|---|---|"]
    for gid, gtext in goal_map.items():
        acs = [a for a, (gs, _) in ac_map.items() if gid in gs]
        marks = ", ".join(f"{a} {icon[res.get(a, (None,))[0]]}" for a in acs) or "—"
        met = bool(acs) and all(res.get(a, (None,))[0] == "pass" for a in acs)
        lines.append(f"| **{gid}** {gtext} | {marks} | {'met' if met else 'not met'} |")
    lines.append("")

    if ac_map:
        lines += ["## Acceptance criteria", ""]
        for aid, (gs, text) in ac_map.items():
            status, evidence = res.get(aid, (None, ""))
            detail = re.sub(rf"^[-*]\s*{aid}\b\s*[:\-–—]?\s*", "", evidence)
            lines.append(f"- {icon[status]} **{aid}** ({', '.join(gs)}): {text}" + (f"  \n  {detail}" if detail else ""))
        lines.append("")

    if nodes:
        lines += ["## Work", ""]
        node_icon = {"complete": "✅", "failed": "❌", "blocked": "🚫", "in_progress": "⏳"}
        for n in nodes:
            covers = ", ".join(n.get("covers", []))
            lines.append(f"- {node_icon.get(n.get('status'), '⬜')} `{n['id']}` {n.get('name', '')}" + (f" (covers {covers})" if covers else ""))
        lines.append("")

    for name in ("Deviations", "Follow-ups"):
        body = section(exec_text, name).strip()
        lines += [f"## {name}", "", body or "None", ""]

    base = wf.data.get("git_base")
    stat = git_diff_stat(wf.root, base) if base else ""
    if stat:
        lines += ["## Changes", "", f"Since `{base[:12]}` (plan approval):", "", "```", stat, "```", ""]
    return "\n".join(lines).rstrip() + "\n"
