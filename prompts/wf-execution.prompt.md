# Execution Stage — Intent-First Workflow

You are entering the **Execution Stage** of the Intent-First workflow.

## Your Role

Implement the approved plan with real-time progress tracking. Follow the plan exactly.

## Usage

```
/wf-execution <workflow-number>
```

## Prerequisites

- `plan.md` must be **Approved — Locked**
- If not, redirect to `/wf-plan` first

## Process

### 1. Initialize

1. Read `workflow/<number>/plan.md` completely
2. Create progress checklist in `execution.md`
3. Record start time

### 2. Execute

For each step in the plan:

1. **Mark step "In Progress"** in execution.md with timestamp
2. **Implement exactly as planned** — use exact signatures, handle all described edge cases
3. **Record completion** — mark ✅ with notes
4. **Run quality checks** — tests, types, linting after each major change

### 3. Handle Issues

If **anything** deviates from the plan:

1. **Stop** execution
2. **Document** in execution.md (issue or deviation)
3. **Propose** resolution
4. **Get human approval** before continuing

### 4. Continuous Updates

Update `execution.md` after every significant action:

```markdown
### [YYYY-MM-DD HH:MM UTC] - Agent: [Name]
**Action:** [What was done]
**Status:** ✅ Success / ⚠️ Issue / ❌ Blocked
**Notes:** [Details]
```

### 5. Final Validation

Before marking complete:

- [ ] All plan steps completed
- [ ] All tests passing
- [ ] All quality gates met
- [ ] All deliverables completed
- [ ] No unresolved issues
- [ ] All deviations documented and approved

## Rules

- ❌ Never skip steps from the plan
- ❌ Never implement differently without approval
- ❌ Never ignore failing tests
- ❌ Never batch updates — update execution.md continuously
- ✅ Follow plan exactly as specified
- ✅ Document every deviation with reason
- ✅ Get human approval for ANY change from plan
- ✅ Run tests after major changes

## After Completion

1. Update execution.md status: `Complete`
2. Wait for instruction to proceed to `/wf-artifacts`
