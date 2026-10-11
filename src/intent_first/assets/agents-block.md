## Intent-First

This repo uses Intent-First for non-trivial changes: **Intent → Spec → Plan → Execution**, each stage approved by the human before the next starts. The spec says what and why; the plan says how. Goals (`G1`) trace to acceptance criteria (`AC1`), then to plan nodes, then to results.

- Workflows live in `.intent-first/workflows/<ID>/`. `intent-first status` shows where each one stands.
- Skills: `intent-first` (start/resume), `intent-spec`, `intent-plan`, `intent-execute`, `intent-yolo`.
- Never edit an approved stage file, `state.json` or `report.md`. Never run `intent-first reopen`, `deactivate`, `uninstall` or `config set`; ask the human.
- While a workflow is active, don't change project files until its plan is approved.
- Small, fully described fixes don't need a workflow.
