---
name: intent-spec
description: Write the spec stage of an Intent-First workflow from its approved intent. Use for /intent-spec <ID>, when asked to draft or revise a workflow's spec, or when a workflow's current stage is spec.
license: MIT
---

# Intent-First: Spec

Input: a workflow ID (ask if missing). Read `.intent-first/workflows/<ID>/intent.md`; write `spec.md` in the same folder. Shared rules are in the `intent-first` skill.

First run `intent-first status <ID>`. The intent must be approved; if it is not, finish it with the human first.

## Steps

1. **Understand.** Read `intent.md` fully. Explore the parts of the codebase it touches: conventions, existing code to reuse, constraints. Use a subagent for broad searches if your tool has one.
2. **Clarify before drafting.** Map every intent item to how it will be met. Ask the human about anything ambiguous now rather than guessing.
3. **Research.** For each external library or API the design depends on, check the current official docs for the version the project uses. Note what you relied on under `## Research Notes`.
4. **Draft `spec.md`** using the template's sections:
   - Overview: each intent item → the design element that satisfies it
   - Design Decisions: context, options, decision, why (only decisions that matter)
   - Interfaces: public APIs, signatures, data shapes, as contracts, not code
   - Constraints: performance, security, compatibility, edge cases
   - Quality Gates: measurable checks (test commands, benchmarks, acceptance criteria)
   - Deliverables: one per intent item, with no orphans in either direction
   - Open Questions: must be empty to approve
   Scale the spec to the change; a small feature gets a short spec. No implementation code.
5. **Review.** Run `intent-first check <ID> spec` and fix every issue. Re-read `intent.md` and confirm everything is covered and nothing extra crept in. If you can start a subagent, have a fresh one review `spec.md` against `intent.md` and report gaps; fix them.
6. **Ask for approval.** Summarise the key decisions and risks in a few lines. Ask the human to review `spec.md` and approve it or say what to change. Revise until they approve.
7. **Lock.** On approval, run `intent-first approve <ID> spec`. The next step is `intent-plan <ID>`.
