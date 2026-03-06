# Intent-First Workflow — Agent Rules
#
# Add this to your AI coding tool's instruction file to enable
# the Intent-First agentic workflow in your project.
#
# For tool-specific locations, see the install script or README.

## Intent-First Agentic Workflow

This project uses the **Intent-First** workflow for complex, multi-step tasks.

### When to Use

Use this workflow for:
- Complex multi-step features requiring design decisions
- Architectural changes affecting multiple components
- High-risk changes where mistakes are costly
- Features requiring clear audit trail

Do NOT use for:
- Simple bug fixes (< 3 files)
- Documentation updates
- Configuration tweaks
- Trivial changes the user describes completely

### Workflow Stages

```
Intent → Spec → Plan → Execution → Artifacts
(human)  (agent) (agent)  (agent)     (agent)
         ↑ approval ↑ approval
```

**Every stage transition requires explicit human approval.**

### Stage Rules

**Intent** (human only):
- Never edit intent.md as an agent
- Read it thoroughly before any work
- Ask clarifying questions if unclear (<80% confidence)

**Spec** (`/wf-spec <number>`):
- Focus on WHAT and HOW (design), not implementation
- Include design decisions, public interfaces, quality gates
- Document deliverables and pass conditions
- Never proceed without human approval

**Plan** (`/wf-plan <number>`):
- Must have approved, locked spec first
- Follow spec decisions strictly — 100% compliance
- Include all file paths, function signatures with types
- Detailed enough that no design decisions remain
- Never proceed without human approval

**Execution** (`/wf-execution <number>`):
- Must have approved, locked plan first
- Follow plan exactly — any deviation needs human approval
- Update execution.md continuously (not batched)
- Document all issues and resolutions immediately

**Artifacts** (`/wf-artifacts <number>`):
- Must have completed execution with all tests passing
- Document code changes, test results, design decisions
- Capture lessons learned
- Suggest follow-up work

### Critical Rules

1. **No auto-proceed**: Never move to next stage without human approval
2. **Stage locking**: Once approved and next stage begins, previous stage cannot be edited
3. **Confidence threshold**: If <80% confident at any point, stop and ask human
4. **Decision tracking**: All decisions must record datetime (UTC) and decision maker
5. **No reversal**: Locked stages are immutable. Create new workflow if major changes needed
6. **100% plan compliance**: During execution, any deviation requires documented human approval

### Creating a New Workflow

Run the CLI or manually create `workflow/XXX/` with these files:
- `intent.md` — Human-written goals (human only)
- `spec.md` — Technical specification (agent drafts, human approves)
- `plan.md` — Implementation plan (agent drafts, human approves)
- `execution.md` — Progress tracking (agent updates continuously)
- `artifacts.md` — Final outcomes (agent documents)

### Stage Prompts

Agents use these prompts to work on each stage:
- `/wf-spec <number>` — Draft or improve specification
- `/wf-plan <number>` — Create implementation plan
- `/wf-execution <number>` — Execute plan with progress tracking
- `/wf-artifacts <number>` — Document final outcomes

For detailed stage instructions, read the corresponding prompt file in the `prompts/` directory (or `.github/prompts/`, `.cursor/prompts/`, etc. depending on your tool).
