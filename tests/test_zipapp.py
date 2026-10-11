"""The single-file zipapp works on the running Python (CI runs this on 3.9 and 3.13)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ZipappTest(unittest.TestCase):
    def test_build_and_run(self):
        subprocess.run([sys.executable, str(ROOT / "scripts/build_pyz.py")], check=True, capture_output=True)
        pyz = ROOT / "dist/intent-first.pyz"
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            for args in (["init", "--tools", "all"], ["new", "w"], ["status", "w"], ["doctor"]):
                r = subprocess.run([sys.executable, str(pyz), *args], cwd=tmp, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace")
                self.assertEqual(r.returncode, 0, f"{args}: {r.stdout}{r.stderr}")
            self.assertTrue((Path(tmp) / ".agents/skills/intent-spec/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
