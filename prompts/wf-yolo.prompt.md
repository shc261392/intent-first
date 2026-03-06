# YOLO Mode — Intent-First Workflow

You are entering **YOLO Mode** of the Intent-First workflow. This is the accelerated path for high-confidence work.

## Your Role

Run the full Intent-First workflow (Spec → Plan → Execute → Artifacts) in a single pass, auto-approving stages when your confidence is ≥85%.

## Usage

```
/wf-yolo <ID>
```

Or with inline intent (no intent file required):

```
/wf-yolo <ID> <intent description>
```

ID is the workflow directory name (number or slug, e.g. `1`, `add-auth`).

## How It Works

1. If a `workflow/<ID>/s1_intent.md` exists, read it as the intent source
2. If an inline intent was provided instead, create `s1_intent.md` from the inline text
3. Run through Spec → Plan → Execute → Artifacts sequentially
4. **Auto-approve** any stage where your confidence is **≥85%**
5. **Pause and present to human** if confidence drops **<85%** at any decision point

## Critical Rules

- ❌ **Never use ask_question or equivalent tools** — either proceed (≥85%) or pause with a summary
- ❌ Never lower your confidence threshold to avoid pausing — be honest
- ❌ Never skip stages — every stage still produces its document
- ✅ **Highlight every auto-approved decision** in the artifacts with `[YOLO-AUTO]` tag
- ✅ Record your confidence score for each stage transition
- ✅ If you pause, present a clear summary of what's done and what triggered the pause
- ✅ Follow all other Intent-First rules (stage locking, decision tracking, no reversal)

## Process

### 1. Capture Intent

- Read `s1_intent.md` or create it from inline input
- Identify all scopes and requirements

### 2. Spec (auto-approve if ≥85%)

- Draft `s2_spec.md` with architecture, interfaces, quality gates
- Rate confidence 0–100% using the scoring model in RULES
- If **≥85%**: mark `[YOLO-AUTO] Approved`, run `intent-first lock <ID> spec`, and continue
- If **<85%**: pause, present spec to human, wait for approval

### 3. Plan (auto-approve if ≥85%)

- Draft `s3_plan.md` from the spec
- Rate confidence 0–100% using the scoring model in RULES
- If **≥85%**: mark `[YOLO-AUTO] Approved`, run `intent-first lock <ID> plan`, and continue
- If **<85%**: pause, present plan to human, wait for approval

### 4. Execute

- Follow the plan exactly
- Track progress in `s4_execution.md`
- On any deviation or issue:
  - If resolution confidence **≥85%**: resolve and tag `[YOLO-AUTO]`
  - If **<85%**: pause, present the issue, wait for human decision

### 5. Artifacts

- Document everything in `s5_artifacts.md`
- Include a **YOLO Decision Log** section listing every `[YOLO-AUTO]` decision:

```markdown
## YOLO Decision Log

| # | Stage | Decision | Confidence | Rationale |
|---|-------|----------|------------|-----------|
| 1 | Spec  | Chose REST over GraphQL | 97% | Single consumer, no nested queries needed |
| 2 | Plan  | Added input validation middleware | 96% | Standard pattern, matches existing codebase |
```

## When to Use YOLO Mode

✅ **Good fit:**

- Tasks with clear, well-scoped intent
- Patterns you've used before in this codebase
- Changes where the design is obvious (CRUD, standard patterns)
- Solo developer who trusts agent judgment

❌ **Bad fit:**

- Architectural decisions with unclear trade-offs
- Security-sensitive changes
- Multi-team coordination
- First time working in an unfamiliar codebase

## Confidence Calibration

Use the confidence scoring model defined in the project rules (RULES.md). Score across Knowledge, Complexity, Consistency, and Risk factors for a 0–100 total.

- **85–100**: High confidence → auto-approve, tag `[YOLO-AUTO]`
- **70–84**: Good confidence but notable gaps → pause, present reasoning
- **<70**: Moderate or below → pause, present options explicitly
