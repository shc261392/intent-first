# Intent-First Protocol v3

This is the tool-neutral contract. The `intent-first` CLI implements it, but any tool can read and write the same files.

## Layout

```
.intent-first/
├── workflows/<ID>/          # git-ignored by default
│   ├── intent.md  spec.md  plan.md  execution.md  artifacts.md
│   └── state.json           # see state.schema.json; written only by the CLI
├── active                   # ID of the active workflow (optional, git-ignored)
├── config.json              # {"block_code_before_plan": true, "strict_approval": false}
├── guard.py                 # pre-tool-use hook (committed)
└── manifest.json            # what `init` installed, for `uninstall`
```

`<ID>` matches `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`.

## Stages

`intent → spec → plan → execution → artifacts`. A stage is:

| Status | Meaning |
|---|---|
| `approved` | approved by a human; its file is read-only and its SHA-256 is recorded |
| `draft` | open for writing: it is `intent`, or the previous stage is approved |
| `pending` | waiting for the previous stage's approval |

Only the approval fields are stored; the status is derived from them. Approvals are contiguous from `intent`.

## Approval

A stage can be approved when its file passes the stage check:

| Stage | Required `##` sections (★ = must not be empty) |
|---|---|
| intent | Goal★ |
| spec | Overview★, Design Decisions★, Interfaces, Constraints, Quality Gates★, Deliverables★, Open Questions |
| plan | Steps★, Files★, Verification★, Open Questions; and the execution graph has no cycles or unknown dependencies |
| execution | Progress★, Deviations; no unchecked `- [ ]` items; every graph node `complete` |
| artifacts | Summary★, Changes★, Verification★, Follow-ups |

For every stage except intent:

- `## Open Questions` must be empty, `None`, or contain only checked `- [x]` items.
- Lines containing `TODO`, `TBD`, `FIXME` or `XXX` outside code fences need an `[APPROVED-DEFER: <name> <date>]` tag on the same line.

HTML comments are ignored, so templates keep their guidance in comments. Approving with `--force` skips the check and records `"forced": true`.

`reopen <stage>` clears the approval of that stage and every later stage. Only the human runs it.

## Execution graph

The graph lives in `state.json` under `graph.nodes`. Each node has an `id`, a `name`, `depends_on`, a `status` and two timestamps. Status is one of `pending | in_progress | complete | failed | blocked`.

- Nodes are added or removed only while the plan is unapproved.
- Node status changes only while the plan is approved and execution is not.
- A node can start only when all of its dependencies are `complete`.
- When a node fails, its transitive dependents become `blocked`. They return to `pending` once no ancestor is failed.

## Guard rules

On every agent tool call that writes or runs a shell command, the guard blocks:

1. Writes to an approved stage file, to `state.json`, or to `.intent-first/{guard.py,config.json,manifest.json,active}`.
2. Writes to a stage file whose previous stage is not approved.
3. Writes outside `.intent-first/` while an active workflow's plan is unapproved, if `block_code_before_plan` is true.
4. The shell commands `intent-first reopen|deactivate|uninstall|config set`, and `approve` too when `strict_approval` is true.
5. Shell commands that both write (redirection, `rm`, `mv`, `sed -i`, ...) and mention a protected path from rules 1–2.

It blocks by writing a reason to stderr and exiting with status 2. Errors inside the guard itself never block. It is a seatbelt against drift, not a security boundary: a human or a determined agent can always edit the files directly. `check` reports any such edits through the hashes.
