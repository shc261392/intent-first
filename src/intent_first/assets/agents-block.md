## Intent-First

This repo uses Intent-First for non-trivial changes: **Intent → Spec → Plan → Execution → Artifacts**, each stage approved by the human before the next starts.

- Workflows live in `.intent-first/workflows/<ID>/`. `intent-first status` shows where each one stands.
- Skills: `intent-first` (start/resume), `intent-spec`, `intent-plan`, `intent-execute`, `intent-artifacts`, `intent-yolo`.
- Never edit an approved stage file or `state.json`. Never run `intent-first reopen`, `deactivate`, `uninstall` or `config set`; ask the human.
- While a workflow is active, don't change project files until its plan is approved.
- Small, fully described fixes don't need a workflow.
