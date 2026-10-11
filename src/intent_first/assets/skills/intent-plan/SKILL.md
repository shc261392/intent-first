---
name: intent-plan
description: Write the implementation plan and execution graph for an Intent-First workflow from its approved spec. Use for /intent-plan <ID>, when asked to plan a workflow, or when a workflow's current stage is plan.
license: MIT
---

# Intent-First: Plan

Input: a workflow ID. Read `intent.md` and `spec.md` in `.intent-first/workflows/<ID>/`; write `plan.md` and the execution graph. Shared rules are in the `intent-first` skill.

The spec must be approved (`intent-first status <ID>`). Its decisions are binding. If you disagree with one, raise it as an open question; never deviate silently.

## Steps

1. **Research the code you will touch:** exact files, functions, patterns to follow, tests to extend, commands that verify the work.
2. **Split the work into graph nodes.** A node is a unit you can finish and verify on its own. Register each node and its dependencies:
   ```
   intent-first graph add <ID> <node-id> --name "what it does" [--deps other-node,another]
   intent-first graph show <ID>
   ```
   Nodes without a dependency path between them can run in parallel.
3. **Write `plan.md`:**
   - Steps: a subsection per node with files, functions and signatures, behaviour, and tests. It must be concrete enough that execution needs no design decisions.
   - Files: every path to create or modify, and why
   - Verification: exact commands, each mapped to a spec Quality Gate
   - Decisions: plan-level choices, each traced to the spec
   - Open Questions: must be empty to approve
4. **Review.** Run `intent-first check <ID> plan` (it also validates the graph) and fix every issue. Confirm each spec deliverable and quality gate is covered by a node and a verification step. If you can start a subagent, have a fresh one review the plan against the spec.
5. **Ask for approval** with a short summary: nodes, order, risky parts. Revise until approved.
6. **Lock.** On approval, run `intent-first approve <ID> plan`. Project files may be changed from now on. The next step is `intent-execute <ID>`.
