# Specification Stage — Intent-First Workflow

You are entering the **Specification Stage** of the Intent-First workflow.

## Your Role

Draft a technical specification from the human-written intent document.

## Usage

```
/wf-spec <ID>
```

ID is the workflow directory name (number or slug, e.g. `1`, `add-auth`).

## Process

### 1. Read Intent

- Open `workflow/<ID>/s1_intent.md`
- Identify all scopes and requirements
- Note ambiguities

### 2. Draft Specification

Create `workflow/<ID>/s2_spec.md` with these required sections:

1. **Overview** — How this addresses the intent
2. **Design Decisions** — Architecture patterns, key technical choices
3. **Public Interfaces** — APIs, function signatures, component props
4. **Constraints & Requirements** — Performance, compatibility, security
5. **Quality Gates** — Testing requirements, benchmarks, documentation
6. **Deliverables** — Clear, measurable outcomes
7. **Pass Conditions** — Completion criteria checklist

### 3. Self-Assessment

- Rate confidence 0–100% using the scoring model in project rules
- If **<70%** on any decision → flag for human review immediately
- Document assumptions

### 4. Request Human Approval

- Present spec summary to human
- Highlight uncertainties
- **Do NOT proceed to planning without explicit approval**

## Rules

- ❌ Never proceed without human approval
- ❌ Never make up requirements not in the intent
- ❌ Never edit s1_intent.md
- ❌ Never include implementation details (save for plan stage)
- ✅ Focus on "what" and "how" from a design perspective
- ✅ Include complete quality gates and pass conditions
- ✅ Document decision rationale with timestamps
- ✅ Flag <70% confidence areas immediately

## After Approval

1. Update s2_spec.md: `Human Approval: [Name] on [Date]`
2. Mark status: `Approved — Locked`
3. Run in terminal: `intent-first lock <ID> spec` to enforce read-only
4. Wait for instruction to proceed to `/wf-plan`
