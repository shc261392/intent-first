<div align="center">

# Intent-First

![intent-first](https://github.com/user-attachments/assets/1dc5ab56-b597-4cb2-a349-b6c4c19cfa03)

**Stop your coding agent from guessing.**

A lightweight, pluggable protocol: **Intent → Spec → Plan → Execution → Artifacts**, approved by you between stages and enforced by your agent's own hooks.

Works with **GitHub Copilot · Claude Code · Cursor · OpenAI Codex · OpenCode**

[![CI](https://github.com/shc261392/intent-first/actions/workflows/ci.yml/badge.svg)](https://github.com/shc261392/intent-first/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

</div>

---

## What it is

You write the intent. The agent designs, plans, builds and documents it, and each stage waits for your approval. The point is to make the agent ask about intent first instead of discovering wrong assumptions 500 lines into a diff.

- **Pluggable.** It installs in each agent's native format: [Agent Skills](https://github.com/agentskills/agentskills), `AGENTS.md`, and that agent's hooks. `intent-first uninstall` removes exactly what was added and leaves your own config intact.
- **Lightweight.** The CLI is a single 35 KB Python file with no dependencies. It adds under 100 words of always-on context; stage instructions load only when they are used.
- **Enforced, not just requested.** A pre-tool-use hook blocks edits to approved stages, writing a stage out of order, and code changes before the plan is approved. Approved files are hashed, so later tampering shows up in `intent-first check`.
- **Checkable.** A stage can't be approved with empty required sections, open questions, unchecked tasks, unfinished graph nodes or unapproved `TODO`s.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/shc261392/intent-first/main/install.sh | sh
```

This downloads `intent-first.pyz` from the latest GitHub release and verifies it against `SHA256SUMS`. Releases also carry [build provenance attestations](https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations) (`gh attestation verify intent-first.pyz -R shc261392/intent-first`). Pin a version with `INTENT_FIRST_VERSION=v3.0.0`.

You can also use [uv](https://docs.astral.sh/uv/) or pipx:

```bash
uv tool install git+https://github.com/shc261392/intent-first@v3.0.0
uvx --from git+https://github.com/shc261392/intent-first@v3.0.0 intent-first init   # no install at all
```

Requires Python 3.9+.

## Set up a project

```bash
cd your-project
intent-first init                      # detects your agents; or:
intent-first init --tools claude,codex # any of: copilot, claude, cursor, codex, opencode, all
```

Commit the files it creates. Workflow data under `.intent-first/workflows/` is git-ignored by default.

| Installed | Read by |
|---|---|
| `AGENTS.md` (marked block) | Copilot, Cursor, Codex, OpenCode |
| `.agents/skills/intent-*/SKILL.md` | Copilot, Cursor, Codex, OpenCode |
| `CLAUDE.md` block, `.claude/skills/`, hook in `.claude/settings.json` | Claude Code (Copilot CLI also reads this hook) |
| `.github/hooks/intent-first.json` | Copilot CLI, cloud agent, VS Code |
| `.cursor/hooks.json` (`preToolUse`, `beforeShellExecution`) | Cursor |
| `.codex/hooks.json` | Codex (trust it once via `/hooks`) |
| `.opencode/plugins/intent-first.js`, `.opencode/commands/` | OpenCode |
| `.intent-first/guard.py`, `config.json`, `manifest.json` | all hooks |

Re-run `intent-first init` to update or to change tools. `intent-first doctor` checks the installation.

## Use it

```bash
intent-first new add-auth      # creates .intent-first/workflows/add-auth/ and makes it active
```

Write the **Goal** in `intent.md`, or ask your agent to help draft it. Then work stage by stage:

| You say | The agent | Then |
|---|---|---|
| "approve the intent" | runs `intent-first approve add-auth intent` | |
| `/intent-spec add-auth` | explores, researches, writes `spec.md`, asks what's unclear | you review → approve |
| `/intent-plan add-auth` | writes `plan.md` and an execution graph of work nodes | you review → approve; code edits unlock |
| `/intent-execute add-auth` | implements node by node, logs progress, asks before deviating | you review → approve |
| `/intent-artifacts add-auth` | documents what shipped, verification, follow-ups | you approve; workflow closes |

How you invoke a skill depends on the agent: `/intent-spec` in Claude Code, Copilot, Cursor and OpenCode, `$intent-spec` in Codex. Or just ask: "continue the intent-first workflow".

Want speed? `/intent-yolo add-auth <intent>` runs every stage in one pass. The agent approves on your behalf only while there are no open questions, and tags its assumptions `[YOLO-ASSUMPTION]`.

```bash
intent-first status [ID]            # where a workflow stands (--json for agents)
intent-first list                   # all workflows
intent-first check ID [stage]       # what blocks approval; detects edits after approval
intent-first approve ID [stage]     # approve and lock (records your name)
intent-first reopen ID stage        # human only: unlock a stage and every stage after it
intent-first new name --parent ID   # follow-up workflow
intent-first deactivate             # human only: allow unrelated code edits
intent-first graph add|rm|set|show|ready ID ...
intent-first config set name "Ann Lee"
intent-first config set block_code_before_plan false
intent-first config set strict_approval true   # only the human may run `approve`
intent-first uninstall [--purge]
```

## What the guard enforces

The guard is the hook every agent runs before a tool call. It blocks the call and tells the agent why when it would:

- edit an approved stage file, `state.json`, or a file the CLI owns;
- write `plan.md` before the spec is approved (and likewise for every stage);
- change project files while the active workflow's plan is unapproved;
- run `intent-first reopen`, `deactivate`, `uninstall` or `config set` (and `approve` under `strict_approval`).

It is a **seatbelt, not a sandbox**. It catches drift and scope creep; it doesn't defend against an agent that is determined to get around it. Errors in the guard itself never block your agent. The full rules are in [`spec/PROTOCOL.md`](spec/PROTOCOL.md).

## When to use it

**Use it** for features that touch several files, architectural changes, anything where "just do it" leads to rework. **Skip it** for one-line fixes and changes you can fully describe in a sentence. Run `intent-first deactivate` (or don't create a workflow) and talk to your agent normally.

| Stage | Reasoning depth | Model tier |
|---|---|---|
| Spec, Plan | Deep: architecture, trade-offs | Strongest available |
| Execution | Moderate: follows a locked plan | Mid-tier |
| Artifacts | Light: structured documentation | Lightweight |

## Upgrading from v2

v3 is a breaking release. Run `intent-first migrate`, then `intent-first init`. See [CHANGELOG.md](CHANGELOG.md).

## FAQ

<details>
<summary><b>Can I skip stages?</b></summary>
No, that's the point. Use <code>/intent-yolo</code> for speed: it still runs every stage but approves for you while nothing is uncertain.
</details>

<details>
<summary><b>The spec turned out wrong after planning. Now what?</b></summary>
Run <code>intent-first reopen ID spec</code> yourself. That unlocks the spec and every later stage. For a big change of direction, start a new workflow with <code>--parent</code> instead.
</details>

<details>
<summary><b>Why is workflow data git-ignored?</b></summary>
It is process, like chat history. The artifacts stage hands you a summary for the commit message or PR. Remove the <code>.gitignore</code> lines if your team wants workflows in git.
</details>

<details>
<summary><b>Do I need the CLI for the agent to follow the workflow?</b></summary>
The skills call it for state changes (approve, graph, check). The file layout and rules in <a href="spec/PROTOCOL.md">spec/PROTOCOL.md</a> are tool-neutral, so another implementation can use the same files.
</details>

## License

[MIT](LICENSE)
