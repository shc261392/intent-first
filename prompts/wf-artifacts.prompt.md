# Artifacts Stage — Intent-First Workflow

You are entering the **Artifacts Stage** of the Intent-First workflow.

## Your Role

Document final outcomes, capture lessons learned, and close the workflow.

## Usage

```
/wf-artifacts <workflow-number>
```

## Prerequisites

- `execution.md` shows status **Complete**
- All tests passing, all deliverables met
- If not, redirect to `/wf-execution` first

## Process

### 1. Verify Completion

- [ ] All plan steps marked complete
- [ ] All spec deliverables met
- [ ] All quality gates passed
- [ ] No unresolved issues

### 2. Gather Information

Collect from:

- `intent.md` — Original goals
- `spec.md` — Design decisions
- `plan.md` — Implementation details
- `execution.md` — What actually happened
- Git diff — Actual file changes
- Test results — Quality verification

### 3. Document Artifacts

Create `workflow/<number>/artifacts.md` with:

1. **Summary** — What was accomplished, how it fulfills intent
2. **Code Changes** — Files created, modified, deleted (with links)
3. **Test Results** — Unit, integration, E2E, quality checks
4. **Design Decisions** — Context, options considered, rationale
5. **Lessons Learned** — What went well, what to improve
6. **Next Steps** — Follow-up work, backlog suggestions
7. **Related Workflows** — Links to predecessor/successor workflows

### 4. Extract Reusable Knowledge

- Patterns to document
- Conventions discovered
- Recommendations for future work

## Rules

- ❌ Never finalize if execution is incomplete
- ❌ Never skip lessons learned
- ❌ Never leave placeholder text
- ✅ Be thorough and honest about outcomes
- ✅ Document both successes and challenges
- ✅ Include all test results
- ✅ Suggest concrete next steps

## Completion

1. Update status: `Complete`
2. Record completion timestamp
3. Present summary to human
4. Workflow is now closed
