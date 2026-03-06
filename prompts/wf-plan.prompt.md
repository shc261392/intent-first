# Planning Stage — Intent-First Workflow

You are entering the **Planning Stage** of the Intent-First workflow.

## Your Role

Create a detailed implementation plan from the approved specification.

## Usage

```
/wf-plan <workflow-number>
```

## Prerequisites

- `spec.md` must be **Approved — Locked**
- If not, redirect to `/wf-spec` first

## Process

### 1. Review Specification

- Read `workflow/<number>/spec.md` completely
- Understand all design decisions and constraints
- Note quality gates and deliverables

### 2. Research Codebase

- Find similar patterns
- Identify files that need modification
- Understand current architecture

### 3. Draft Plan

Create `workflow/<number>/plan.md` with these required sections:

1. **Implementation Overview** — Summary of approach
2. **Files to be Modified** — New, modified, deleted files with purposes
3. **Detailed Implementation** — For each component:
   - Full function signatures with types
   - Purpose and behavior
   - Parameters and return values
   - Implementation notes and edge cases
4. **Testing Strategy** — Unit, integration, E2E test cases
5. **Validation Steps** — How to verify completion
6. **Dependencies & Prerequisites** — Required setup

### 4. Verify Completeness

- [ ] All spec deliverables addressed
- [ ] All public interfaces included
- [ ] Test coverage meets quality gates
- [ ] Function signatures are complete and typed
- [ ] Edge cases identified

### 5. Request Human Approval

- **Do NOT proceed to execution without explicit approval**

## Rules

- ❌ Never proceed without approved spec
- ❌ Never deviate from spec decisions
- ❌ Never make design decisions (those belong in spec)
- ✅ Strictly follow all spec decisions
- ✅ Include complete function signatures with types
- ✅ Plan comprehensive test coverage
- ✅ Mark as "Derived From: spec.md (locked)"

## After Approval

1. Update plan.md: `Human Approval: [Name] on [Date]`
2. Mark status: `Approved — Locked`
3. Wait for instruction to proceed to `/wf-execution`
