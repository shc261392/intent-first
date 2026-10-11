---
name: intent-first
description: Start, resume or check an Intent-First workflow (Intent → Spec → Plan → Execution → Artifacts, each approved by the human). Use when the user wants a non-trivial change designed and planned before code is written, mentions intent-first, or asks where a workflow stands.
license: MIT
---

# Intent-First

Intent-First keeps the human in charge of *what* gets built. Each workflow is a folder `.intent-first/workflows/<ID>/` with five stage files and a `state.json` that only the `intent-first` CLI writes.

| Stage | File | Written by | Skill |
|---|---|---|---|
| Intent | `intent.md` | the human (you may help) | this one |
| Spec | `spec.md` | you | `intent-spec` |
| Plan | `plan.md` + execution graph | you | `intent-plan` |
| Execution | `execution.md` + the code | you | `intent-execute` |
| Artifacts | `artifacts.md` | you | `intent-artifacts` |

`intent-yolo` runs every stage in one pass when the user explicitly asks for it.

## Start a workflow

1. `intent-first new [name]` creates the folder and makes it the active workflow. Tell the user the ID.
2. Help the human write `intent.md`: Goal (required), Context, Constraints, Out of Scope. Ask about anything unclear; never invent goals.
3. When the human confirms the intent, run `intent-first approve <ID> intent`, then continue with `intent-spec`.

## Resume

Run `intent-first status <ID> --json`. `current_stage` is the first stage that is not approved; load that stage's skill.

## Rules for every stage

- **Approval comes from the human only**, in clear words ("approve", "LGTM", "yes, lock it"). Then run `intent-first approve <ID> <stage>`; it records their name and locks the file. If the hook blocks it (strict approval), ask the human to run that command. Questions, partial feedback or silence are not approval.
- **Before asking for approval**, run `intent-first check <ID> <stage>` and fix everything it reports.
- **Uncertain? Ask.** Put unresolved points under `## Open Questions` and ask the human. A stage with open questions cannot be approved.
- **Approved files are final.** Never edit an approved stage file, `state.json` or other `.intent-first/` files the CLI owns. Never run `intent-first reopen`, `deactivate`, `uninstall` or `config set`; those are the human's. If something approved is wrong, say so and let the human reopen it or start a new workflow.
- **No code before the plan is approved** while a workflow is active. A hook enforces this where installed.
- **Nothing is dropped silently.** Postponing anything needs the human's OK, recorded as `[APPROVED-DEFER: <name> <date>]`.
- **Write as you go.** The stage file is the memory shared across sessions and agents; keep it current.

## CLI

```
intent-first status [ID] [--json]       intent-first new [name] [--parent ID]
intent-first check ID [stage]           intent-first approve ID stage
intent-first graph add|set|show|ready ID ...
```
