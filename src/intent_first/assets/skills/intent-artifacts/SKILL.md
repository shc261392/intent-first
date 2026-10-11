---
name: intent-artifacts
description: Close an Intent-First workflow by documenting what was built, how it was verified, and follow-ups. Use for /intent-artifacts <ID>, or when a workflow's current stage is artifacts.
license: MIT
---

# Intent-First: Artifacts

Input: a workflow ID. Read all earlier stage files in `.intent-first/workflows/<ID>/`; write `artifacts.md`. Shared rules are in the `intent-first` skill.

Execution must be approved (`intent-first status <ID>`).

## Steps

1. **Gather facts:** the diff (`git diff --stat` plus the key hunks), test and verification results, and deviations from `execution.md`.
2. **Write `artifacts.md`:**
   - Summary: what was built, measured against each intent item
   - Changes: files changed and why
   - Verification: the commands run and their results
   - Lessons: what to do differently next time (optional)
   - Follow-ups: each one a candidate new workflow, or "None"
   Report facts. If something in the intent was not delivered, say so plainly.
3. **Follow-ups.** For each follow-up the human wants to pursue, run `intent-first new <name> --parent <ID>` and draft its `intent.md` from the follow-up.
4. **Close.** Run `intent-first check <ID> artifacts`, fix any issues, and ask for approval. On approval, run `intent-first approve <ID> artifacts`; this closes the workflow and clears it as active.
5. Workflow files are git-ignored by default. Offer the Summary as a commit message or pull request description.
