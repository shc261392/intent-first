# Intent-First Protocol v3

This is the tool-neutral contract. The `intent-first` CLI implements it, but any tool can read and write the same files.

## Layout

```
.intent-first/
├── workflows/<ID>/          # git-ignored by default
│   ├── intent.md  spec.md  plan.md  execution.md
│   ├── state.json           # see state.schema.json; written only by the CLI
│   └── report.md            # generated when execution is approved
├── active                   # ID of the active workflow (optional, git-ignored)
├── config.json              # {"block_code_before_plan": true, "strict_approval": false}
├── guard.py                 # pre-tool-use hook (committed)
└── manifest.json            # what `init` installed, for `uninstall`
```

`<ID>` matches `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`.

## Stages

`intent → spec → plan → execution`. Each one is a gate the human approves.

| Stage | Answers | Seen from | Reader | Must not contain |
|---|---|---|---|---|
| intent | What outcome do we want, and why? | the user | everyone | solutions |
| spec | What will be true, and why this design? | outside the code | the human approving it | file paths, task order, code |
| plan | How, and in what order? | inside the code | the agent executing it | new behaviour, interfaces or decisions |
| execution | Did we do it, and what proves it? | the evidence | the human approving it | unrecorded deviations |

Two tests separate spec from plan. The spec must stay valid if the plan is thrown away and redone. A reviewer must be able to accept or reject the finished work from the spec alone. When planning uncovers a missing decision, it goes back to the spec as an open question; the plan never makes it.

Each stage is in one of three states:

| Status | Meaning |
|---|---|
| `approved` | approved by a human; its file is read-only and its SHA-256 is recorded |
| `draft` | open for writing: it is `intent`, or the previous stage is approved |
| `pending` | waiting for the previous stage's approval |

Only the approval fields are stored; the status is derived from them. Approvals are contiguous from `intent`. `reopen <stage>` clears that stage and every later one, and only the human runs it.

## Traceability (intent mapping)

Intent mapping is not a stage. It is a thread of IDs that every gate checks:

```
intent.md     ## Goals                 - G1: outcome, and why
spec.md       ## Acceptance Criteria   - AC1 (G1): observable, testable statement
state.json    graph node               "covers": ["AC1"]
plan.md       ## Verification          - AC1: command or check
execution.md  ## Results               - AC1: pass — evidence
```

## Approval checks

| Stage | Required `##` sections (★ = must not be empty) | Traceability |
|---|---|---|
| intent | Goals★ | goals are numbered `- G<n>:` and unique |
| spec | Summary★, Behaviour★, Interfaces, Decisions★, Acceptance Criteria★, Open Questions | every AC is `- AC<n> (G…):` with known goals; every goal has an AC |
| plan | Approach★, Steps★, Verification★, Open Questions | the graph is non-empty and acyclic; every node covers a known AC; every AC is covered by a node and has a Verification line; `### <node-id>` steps match the nodes 1:1 |
| execution | Progress★, Deviations, Results★ | no unchecked `- [ ]` items; every node `complete`; every AC has a `pass` result, or a `fail` tagged `[APPROVED-DEFER: …]` |

For every stage except intent:

- `## Open Questions` must be empty, `None`, or contain only checked `- [x]` items.
- Lines containing `TODO`, `TBD`, `FIXME` or `XXX` outside code fences need an `[APPROVED-DEFER: <name> <date>]` tag on the same line.

HTML comments are ignored, so templates keep their guidance in comments. `check` also prints non-blocking notes, for example a source-file path in the spec outside `## Interfaces`. Approving with `--force` skips the blocking checks and records `"forced": true`.

## Report

There is no artifacts stage. Approving the plan records `git_base` (HEAD at that moment). Approving execution closes the workflow and writes `report.md`, rendered from the thread:

- goals → criteria → results, with met / not met per goal;
- the work nodes and the criteria each one covered;
- deviations and follow-ups from `execution.md`;
- `git diff --stat` since `git_base`.

`intent-first report <ID>` prints it at any time, for a commit message or pull request description.

## Execution graph

The graph lives in `state.json` under `graph.nodes`. Each node has an `id`, a `name`, `depends_on`, a `status` and two timestamps. Status is one of `pending | in_progress | complete | failed | blocked`.

- Nodes are added or removed only while the spec is approved and the plan is not. Each node covers at least one acceptance criterion.
- Node status changes only while the plan is approved and execution is not.
- A node can start only when all of its dependencies are `complete`.
- When a node fails, its transitive dependents become `blocked`. They return to `pending` once no ancestor is failed.

## Guard rules

On every agent tool call that writes or runs a shell command, the guard blocks:

1. Writes to an approved stage file, to `state.json` or `report.md`, or to `.intent-first/{guard.py,config.json,manifest.json,active}`.
2. Writes to a stage file whose previous stage is not approved.
3. Writes outside `.intent-first/` while an active workflow's plan is unapproved, if `block_code_before_plan` is true.
4. The shell commands `intent-first reopen|deactivate|uninstall|config set`, and `approve` too when `strict_approval` is true.
5. Shell commands that both write (redirection, `rm`, `mv`, `sed -i`, ...) and mention a protected path from rules 1–2.

It blocks by writing a reason to stderr and exiting with status 2. Errors inside the guard itself never block. It is a seatbelt against drift, not a security boundary: a human or a determined agent can always edit the files directly. `check` reports any such edits through the hashes.
