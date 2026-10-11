# Contributing to intent-first

- Code: `src/intent_first/` (stdlib only, Python 3.9+). `guard.py` must stay standalone: it is copied into user projects, so it can't import the package.
- Shipped content: `src/intent_first/assets/` (skills, templates, the AGENTS.md block, the OpenCode plugin). Keep skills tool-neutral and under 500 words each; `tests/test_assets.py` enforces this.
- Protocol changes must update `spec/PROTOCOL.md` and `spec/state.schema.json`.
- Test: `python3 -m unittest discover -s tests`. Lint: `uvx ruff check src tests scripts` and `shellcheck install.sh`.
- Build the single-file CLI: `python3 scripts/build_pyz.py` → `dist/intent-first.pyz`.
- Release: bump `__version__` in `src/intent_first/__init__.py`, update `CHANGELOG.md`, and push a `vX.Y.Z` tag.
