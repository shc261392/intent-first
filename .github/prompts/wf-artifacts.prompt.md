# Artifacts Stage — Intent-First Workflow

You are entering the **Artifacts Stage** of the Intent-First workflow.

## Your Role

Document final outcomes, capture lessons learned, and close the workflow.

## Usage

```
/wf-artifacts <ID>
```

ID is the workflow directory name (number or slug, e.g. `1`, `add-auth`).

## Prerequisites

- `s4_execution.md` shows status **Complete**
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

- `s1_intent.md` — Original goals
- `s2_spec.md` — Design decisions
- `s3_plan.md` — Implementation details
- `s4_execution.md` — What actually happened
- Git diff — Actual file changes
- Test results — Quality verification

### 3. Document Artifacts

Create `workflow/<ID>/s5_artifacts.md` with:

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

1. Update s5_artifacts.md status: `Complete`
2. Record completion timestamp
3. Run in terminal: `intent-first lock <ID> artifacts` to enforce read-only
4. Present summary to human
5. Workflow is now closed
