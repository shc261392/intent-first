---
name: intent-execute
description: Implement an Intent-First workflow's approved plan node by node, tracking progress in execution.md and the execution graph. Use for /intent-execute <ID>, when asked to build or continue building a planned workflow, or when its current stage is execution.
license: MIT
---

# Intent-First: Execution

Input: a workflow ID. Read `spec.md` and `plan.md` in `.intent-first/workflows/<ID>/`; change the code and keep `execution.md` current. Shared rules are in the `intent-first` skill.

The plan must be approved (`intent-first status <ID>`).

## Loop

1. `intent-first graph ready <ID>` lists the nodes whose dependencies are complete.
2. For each ready node:
   - `intent-first graph set <ID> <node> in_progress`
   - Implement exactly what the plan says for that node, then run its tests.
   - Update `execution.md` as you go, not at the end: tick the node under `## Progress` and add a line to `## Timeline` (what changed, test results, problems).
   - `intent-first graph set <ID> <node> complete`, or `failed` if it cannot be done (its dependents become blocked).
   If your tool has subagents, you may run independent ready nodes in parallel. Give each subagent its node's plan section and these rules.
3. Repeat until no nodes remain.

## Deviations

If the plan cannot be followed as written (a wrong assumption, an approach that fails, missing information), stop and ask the human. Describe the problem and propose an option. After they agree, record it under `## Deviations` with who approved it and when, then continue. Never change scope silently, and never skip or weaken a test to get green.

## Finish

1. Run every command under the plan's `## Verification`. All must pass; record the results in `execution.md`.
2. Run `intent-first check <ID> execution` and fix every issue (unchecked items, unfinished nodes).
3. Ask the human to review the changes and approve. On approval, run `intent-first approve <ID> execution`. The next step is `intent-artifacts <ID>`.
