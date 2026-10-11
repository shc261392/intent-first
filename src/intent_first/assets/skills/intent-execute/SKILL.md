---
name: intent-execute
description: Implement an Intent-First workflow's approved plan node by node, record evidence for every acceptance criterion, and close the workflow. Use for /intent-execute <ID>, when asked to build or continue building a planned workflow, or when its current stage is execution.
license: MIT
---

# Intent-First: Execution

Input: a workflow ID. Read `spec.md` and `plan.md` in `.intent-first/workflows/<ID>/`; change the code and keep `execution.md` current. Shared rules are in the `intent-first` skill. The plan must be approved.

## Build

1. `intent-first graph ready <ID>` lists the nodes whose dependencies are complete.
2. For each ready node:
   - `intent-first graph set <ID> <node> in_progress`
   - Implement exactly what the plan's `### <node>` step says, then run its tests.
   - Update `execution.md` as you go: tick the node under `## Progress` and add a line to `## Log`.
   - `intent-first graph set <ID> <node> complete`, or `failed` if it cannot be done (its dependents become blocked).
   If your tool has subagents, you may run independent ready nodes in parallel. Give each one its node's plan section and these rules.
3. Repeat until no nodes remain.

## Deviations

If the plan cannot be followed as written, stop and ask the human. Describe the problem and propose an option. Record what they approve under `## Deviations`, with who approved it and when. If the problem changes behaviour or a decision, it belongs in the spec: say so. Never change scope silently, and never skip or weaken a test to get green.

## Prove and close

1. Run every command under the plan's `## Verification`.
2. Fill `## Results` with one line per acceptance criterion: `- AC1: pass — command and outcome`. A failure stays `fail` with the reason; only the human can accept it, as `[APPROVED-DEFER: <name> <date>]`.
3. List anything that belongs in a new workflow under `## Follow-ups`. For those the human wants, run `intent-first new <name> --parent <ID>`.
4. Run `intent-first check <ID> execution` and fix every issue.
5. Ask the human to review the changes and approve. On approval, run `intent-first approve <ID> execution`. It closes the workflow and writes `report.md`, which traces goals → criteria → work → results with the diff stat. Offer `intent-first report <ID>` as the commit message or pull request description.
