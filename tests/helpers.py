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
    "intent": "# Intent\n\n## Goal\nUsers can log in with GitHub.\n",
    "spec": (
        "# Spec\n\n## Overview\nLogin via OAuth.\n\n## Design Decisions\nUse the provider SDK.\n\n"
        "## Interfaces\nNone\n\n## Constraints\nNone\n\n## Quality Gates\n- `pytest` passes\n\n"
        "## Deliverables\n1. Login button\n\n## Open Questions\nNone\n"
    ),
    "plan": (
        "# Plan\n\n## Steps\n### api\nAdd route.\n\n## Files\n- app.py\n\n## Verification\n- pytest\n\n"
        "## Open Questions\n"
    ),
    "execution": "# Execution\n\n## Progress\n- [x] api: route added\n\n## Deviations\nNone\n",
    "artifacts": (
        "# Artifacts\n\n## Summary\nLogin works.\n\n## Changes\n- app.py\n\n## Verification\npytest: 3 passed\n\n"
        "## Follow-ups\nNone\n"
    ),
}
