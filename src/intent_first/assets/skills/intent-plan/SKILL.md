---
name: intent-plan
description: Write the plan of an Intent-First workflow, meaning how and in what order, as file-level steps and an execution graph covering the approved spec's acceptance criteria. Use for /intent-plan <ID>, when asked to plan a workflow, or when its current stage is plan.
license: MIT
---

# Intent-First: Plan

Input: a workflow ID. Read `intent.md` and `spec.md` in `.intent-first/workflows/<ID>/`; write `plan.md` and the execution graph. Shared rules are in the `intent-first` skill. The spec must be approved.

## What a plan is, and is not

The plan says **how and in what order**, seen from inside the code. Its reader is the agent that will execute it, possibly a different agent in a fresh session.

- It holds: files, functions and signatures, tests, sequencing, how each acceptance criterion is verified, and risks.
- It adds no new behaviour, interfaces or decisions. If you find you need one, the spec is incomplete: add it under Open Questions and tell the human, who can reopen the spec.

## Steps

1. **Research the code you will touch:** exact files, patterns to follow, tests to extend, commands that verify the work.
2. **Split the work into graph nodes.** A node is a unit you can finish and verify on its own, and it serves at least one acceptance criterion:
   ```
   intent-first graph add <ID> <node-id> --covers AC1,AC2 [--deps other-node] --name "what it does"
   intent-first graph show <ID>
   ```
   Every criterion must be covered by some node. Nodes without a dependency path between them can run in parallel.
3. **Write `plan.md`:**
   - Approach: the strategy in a few sentences, and why this order
   - Steps: one `### <node-id>` subsection per node, with files, changes, signatures and tests. It must be concrete enough that execution needs no design decisions.
   - Verification: one line per criterion, `- AC1: exact command or check`
   - Risks: what could go wrong, and the rollback (optional)
   - Open Questions: must be empty to approve
4. **Review.** Run `intent-first check <ID> plan` and fix every issue. It checks the graph, coverage of every criterion, steps against nodes, and a verification line per criterion. If you can start a subagent, have a fresh one check that the plan implements the spec and nothing more.
5. **Ask for approval** with a short summary of the nodes, their order and the risky parts. Revise until the human approves, then run `intent-first approve <ID> plan`. Project files may be changed from then on. Next: `intent-execute <ID>`.
