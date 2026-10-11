---
name: intent-spec
description: Write the spec of an Intent-First workflow, meaning what will be true and why this design, from its approved intent. Use for /intent-spec <ID>, when asked to draft or revise a workflow's spec, or when a workflow's current stage is spec.
license: MIT
---

# Intent-First: Spec

Input: a workflow ID (ask if it is missing). Read `.intent-first/workflows/<ID>/intent.md`; write `spec.md`. Shared rules are in the `intent-first` skill. The intent must be approved (`intent-first status <ID>`).

## What a spec is, and is not

The spec says **what will be true and why this design**, seen from outside the code. Its reader is the human deciding whether this is the right thing to build.

- It holds: behaviour users and callers observe, the contracts others depend on, decisions with the alternatives considered, and acceptance criteria that prove each goal.
- It does not hold: file paths, task order, function bodies or code. Those belong in the plan.
- Test it twice. Would the spec still hold if the plan were thrown away and redone? Could a reviewer accept or reject the finished work using only the spec?

## Steps

1. **Understand.** Read the intent. Explore the codebase only enough to know what is feasible, what already exists, and which conventions and constraints apply.
2. **Clarify first.** For each goal, decide what observable result would prove it. Ask the human about anything ambiguous before drafting.
3. **Research.** Check the current official docs for any external library or API the design depends on, at the version the project uses.
4. **Write `spec.md`:**
   - Summary: the solution in plain sentences
   - Behaviour: flows, states, errors, edge cases
   - Interfaces: APIs, CLI flags, config, data formats ("None" if not applicable)
   - Decisions: context, options, choice, why (only the ones that shape the result)
   - Acceptance Criteria: `- AC1 (G1): observable, testable statement`. Every goal needs at least one; no criterion without a goal.
   - Open Questions: must be empty to approve
   Scale it to the change; a small feature gets a short spec.
5. **Review.** Run `intent-first check <ID> spec`. It verifies that every goal is covered, and notes file-level detail that belongs in the plan. Fix the issues. If you can start a subagent, have a fresh one review `spec.md` against `intent.md` and report gaps.
6. **Ask for approval** with a few lines on key decisions and risks. Revise until the human approves, then run `intent-first approve <ID> spec`. Next: `intent-plan <ID>`.
