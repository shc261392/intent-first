# Changelog

## 3.0.0

A rewrite for agents that support Agent Skills and hooks. It is **breaking**: workflow files, commands and install locations all changed.

### Added

- First-class support for **GitHub Copilot, Claude Code, Cursor, OpenAI Codex and OpenCode**, each in its native format: Agent Skills (`SKILL.md`), `AGENTS.md`, and that tool's hooks or plugin.
- **Guard hook** (`.intent-first/guard.py`). It blocks edits to approved stages, writes that skip a stage, code changes before the plan is approved, and agent use of human-only commands.
- `intent-first check`: deterministic readiness checks (required sections, open questions, unapproved `TODO`s, unchecked tasks, graph state), plus SHA-256 integrity of approved stages.
- `approve`, `reopen`, `activate`/`deactivate`, `doctor`, `uninstall`, and `migrate` (v2 → v3).
- `config set strict_approval true`, so that only the human can approve.
- Blocked actions are logged to `.intent-first/audit.log`.
- Tool-neutral protocol spec (`spec/PROTOCOL.md`) and state schema (`spec/state.schema.json`).
- Releases ship a single-file zipapp plus wheel and sdist, with `SHA256SUMS` and build provenance attestations. `install.sh` verifies the checksum.
- CI on Linux, macOS and Windows with Python 3.9 and 3.13.

### Changed

- License: GPL-3.0 → **MIT**.
- Workflow files: `s1_intent.md`…`s5_artifacts.md` + `status.yml` + `execution-graph.json` → `intent.md`…`artifacts.md` + one `state.json`.
- Commands: `/wf-spec` etc. → skills `intent-spec`, `intent-plan`, `intent-execute`, `intent-artifacts`, `intent-yolo`, plus the `intent-first` entry skill.
- The LLM's self-scored "70% / 85% confidence" gates are replaced by an `## Open Questions` gate that `check` can verify. YOLO approves only while there are no open questions.
- About 7,500 words of always-loaded rules and prompts → about 90 always-on words plus about 1,900 words of skills that load on demand.
- `install.sh` installs only the CLI, from a pinned release, into `~/.local/bin`. It no longer edits shell profiles or projects.
- `graph update --status X` → `graph set ID NODE X`; `graph create` is gone (graphs live in `state.json`).

### Removed

- Phase tracking (`phase-update`, `phase-list`): it cost many tool calls and had no enforcement value.
- The `Workflow Auditor` agent, with its hard-coded models. Stage skills now run `intent-first check` and suggest a fresh-subagent review where the tool supports it.
- `status-update`, `lock`/`unlock` (use `approve`/`reopen`), `link`, `spawn` (use `new --parent`), `validate` (use `check`), `implode` (use `uninstall`), `upgrade` (re-run the installer or `uv tool upgrade`), and network version checks.
- Windsurf, Aider, Cline and Antigravity adapters. These tools can still read the `AGENTS.md` block and `.agents/skills/` where they support them.
- The promptfoo config, which only did string matching. It is replaced by unit tests that lint the skills.

### Migrating from v2

```bash
# install v3 (see README), then in each project:
intent-first migrate   # converts workflows; removes wf-* prompts, the auditor agent and v2 rule one-liners
intent-first init      # installs v3 skills, AGENTS.md block and hooks
```

A v2 `intent-first upgrade` now installs a stub that prints these steps.

`migrate` keeps stage approvals that are contiguous from intent (v2 `locked`/`approved`/`complete`), re-hashes those files, and carries over graph nodes and parent/child links.
