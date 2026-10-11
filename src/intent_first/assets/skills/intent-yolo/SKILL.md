---
name: intent-yolo
description: Run a whole Intent-First workflow (spec, plan, execution, artifacts) in one pass, approving stages on the user's behalf, but only when the user explicitly asks for YOLO mode. Use for /intent-yolo <ID> [intent text].
license: MIT
---

# Intent-First: YOLO

The user wants the structure of the workflow without stopping for review at each stage. You still do every stage properly. You approve each one yourself only while nothing is uncertain.

Input: a workflow ID, optionally with intent text. If the workflow does not exist, run `intent-first new <ID>`. If intent text was given, write it into `intent.md` (Goal, and Constraints if stated) without adding goals of your own.

## Run

For each stage in order (intent, spec, plan, execution, artifacts):

1. Do the stage's work exactly as its skill describes (`intent-spec`, `intent-plan`, `intent-execute`, `intent-artifacts`; load each when you reach it). Intent only needs the user's text.
2. Run `intent-first check <ID> <stage>` and fix every issue.
3. If `## Open Questions` is empty and the check passes, run `intent-first approve <ID> <stage> --yolo` and continue. It records the approval as yours, made on the user's behalf.
4. If anything is genuinely uncertain (a requirement, a risky design choice, a deviation from the plan), **stop and ask the user**. Resume once answered. Minor assumptions go under the stage's Decisions with the tag `[YOLO-ASSUMPTION]`.

YOLO never means skipping verification, weakening tests, or deferring work without the user's OK.

## Report

At the end, give a short report: the stages auto-approved, every `[YOLO-ASSUMPTION]`, the verification results, and the follow-ups.
