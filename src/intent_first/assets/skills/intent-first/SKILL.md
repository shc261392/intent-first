---
name: intent-first
description: Start, resume or check an Intent-First workflow (Intent → Spec → Plan → Execution, each approved by the human). Use when the user wants a non-trivial change designed and planned before code is written, mentions intent-first, or asks where a workflow stands.
license: MIT
---

# Intent-First

Intent-First keeps the human in charge of *what* gets built. Each workflow is a folder `.intent-first/workflows/<ID>/` with four stage files and a `state.json` that only the `intent-first` CLI writes.

| Stage | Answers | Reader | Skill |
|---|---|---|---|
| Intent | What outcome do we want, and why? | everyone | this one |
| Spec | What will be true, and why this design? (outside view) | the human approving it | `intent-spec` |
| Plan | How, and in what order? (inside view) | the agent executing it | `intent-plan` |
| Execution | Did we do it, and what proves it? | the human approving it | `intent-execute` |

`intent-yolo` runs every stage in one pass when the user explicitly asks for it.

## The thread

Goals are traced, not re-stated: intent `G1` → spec `AC1 (G1)` → plan node `--covers AC1` with a Verification line → execution `AC1: pass — evidence`. `intent-first check` enforces every link. When execution is approved, the CLI writes `report.md` from this thread. There is no separate write-up step.

## Start a workflow

1. `intent-first new [name]` creates the folder and makes it the active workflow.
2. Help the human write `intent.md`. Goals go one per line as `- G1: outcome, and why`, plus optional Context, Constraints and Out of Scope. Ask about anything unclear; never invent goals.
3. When the human confirms, run `intent-first approve <ID> intent`, then continue with `intent-spec`.

## Resume

Run `intent-first status <ID> --json`. `current_stage` is the first unapproved stage; load its skill.

## Rules for every stage

- **Approval comes from the human only**, in clear words ("approve", "LGTM"). Then run `intent-first approve <ID> <stage>`; it records their name and locks the file. If the hook blocks it (strict approval), ask the human to run it. Questions, partial feedback or silence are not approval.
- **Before asking for approval**, run `intent-first check <ID> <stage>` and fix everything it reports.
- **Uncertain? Ask.** Put unresolved points under `## Open Questions` and ask. A stage with open questions cannot be approved.
- **Approved files are final.** Never edit them, `state.json`, `report.md` or other files the CLI owns. Never run `intent-first reopen`, `deactivate`, `uninstall` or `config set`. If something approved is wrong, say so; the human can reopen it.
- **No code before the plan is approved** while a workflow is active. A hook enforces this where installed.
- **Nothing is dropped silently.** Postponing anything needs the human's OK, recorded as `[APPROVED-DEFER: <name> <date>]`.
- **Write as you go.** Stage files are the memory shared across sessions and agents.

## CLI

```
intent-first status [ID] [--json]     intent-first new [name] [--parent ID]
intent-first check ID [stage]         intent-first approve ID stage
intent-first graph add|set|show|ready ID ...     intent-first report ID
```
