"""Shared test helpers: run the CLI in an isolated temporary project."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from intent_first import cli  # noqa: E402


class ProjectTestCase(unittest.TestCase):
    """Each test gets a fresh git repo as the project root and a private config home."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="intent-first-test-")).resolve()
        self.addCleanup(self._cleanup)
        self.root = self.tmp / "project"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self._env = {k: os.environ.get(k) for k in ("INTENT_FIRST_ROOT", "XDG_CONFIG_HOME", "INTENT_FIRST_USER")}
        os.environ["INTENT_FIRST_ROOT"] = str(self.root)
        os.environ["XDG_CONFIG_HOME"] = str(self.tmp / "config")
        os.environ["INTENT_FIRST_USER"] = "Tester"

    def _cleanup(self) -> None:
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for dirpath, _dirs, files in os.walk(self.tmp):
            for f in files:
                try:
                    os.chmod(os.path.join(dirpath, f), 0o644)
                except OSError:
                    pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *args: str, expect: int = 0) -> str:
        buf_out, buf_err = io.StringIO(), io.StringIO()
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            try:
                code = cli.main(list(args))
            except SystemExit as exc:  # argparse errors
                code = exc.code if isinstance(exc.code, int) else 1
        output = buf_out.getvalue() + buf_err.getvalue()
        self.assertEqual(code, expect, f"intent-first {' '.join(args)} exited {code}:\n{output}")
        return output

    def wf_path(self, wid: str, name: str) -> Path:
        return self.root / ".intent-first" / "workflows" / wid / name

    def write_stage(self, wid: str, stage: str, text: str) -> None:
        path = self.wf_path(wid, f"{stage}.md")
        os.chmod(path, 0o644)
        path.write_text(text, encoding="utf-8")

    def state(self, wid: str) -> dict:
        return json.loads(self.wf_path(wid, "state.json").read_text(encoding="utf-8"))


GOOD = {
    "intent": "# Intent: GitHub login\n\n## Goals\n- G1: Users can log in with GitHub.\n- G2: Password login keeps working.\n",
    "spec": (
        "# Spec\n\n## Summary\nAdd OAuth login next to passwords.\n\n## Behaviour\nA GitHub button starts OAuth.\n\n"
        "## Interfaces\nNone\n\n## Decisions\nUse the provider SDK.\n\n"
        "## Acceptance Criteria\n- AC1 (G1): GitHub login lands on the dashboard.\n- AC2 (G2): Password login is unchanged.\n\n"
        "## Open Questions\nNone\n"
    ),
    "plan": (
        "# Plan\n\n## Approach\nRoute first, then UI.\n\n## Steps\n### api — callback route\nAdd route in app.py.\n\n"
        "### ui\nAdd the button.\n\n## Verification\n- AC1: `pytest -k github`\n- AC2: `pytest -k password`\n\n"
        "## Open Questions\n"
    ),
    "execution": (
        "# Execution\n\n## Progress\n- [x] api: route added\n- [x] ui: button added\n\n## Deviations\nNone\n\n"
        "## Results\n- AC1: pass — `pytest -k github` (3 passed)\n- AC2: pass — `pytest -k password` (5 passed)\n\n"
        "## Follow-ups\n- Add GitLab login\n"
    ),
}
NODES = (("api", "AC1", ""), ("ui", "AC1,AC2", "api"))


def add_nodes(case: ProjectTestCase, wid: str) -> None:
    for node, covers, deps in NODES:
        args = ["graph", "add", wid, node, "--covers", covers]
        case.run_cli(*(args + (["--deps", deps] if deps else [])))


def complete_nodes(case: ProjectTestCase, wid: str) -> None:
    for node, _, _ in NODES:
        case.run_cli("graph", "set", wid, node, "in_progress")
        case.run_cli("graph", "set", wid, node, "complete")


def approve_through(case: ProjectTestCase, wid: str, last: str) -> None:
    """Write good content and approve every stage up to and including `last`."""
    for stage in ("intent", "spec", "plan", "execution"):
        if stage == "plan":
            add_nodes(case, wid)
        if stage == "execution":
            complete_nodes(case, wid)
        case.write_stage(wid, stage, GOOD[stage])
        case.run_cli("approve", wid, stage)
        if stage == last:
            return
