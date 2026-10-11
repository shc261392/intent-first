#!/usr/bin/env python3
"""Build dist/intent-first.pyz: the whole CLI as one executable file (Python 3.9+, no dependencies)."""

from __future__ import annotations

import shutil
import sys
import tempfile
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    out = ROOT / "dist" / "intent-first.pyz"
    out.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(ROOT / "src" / "intent_first", Path(tmp) / "intent_first",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        zipapp.create_archive(tmp, out, interpreter="/usr/bin/env python3", main="intent_first.cli:_entry", compressed=True)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
