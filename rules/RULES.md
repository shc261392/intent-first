<!-- Intent-First Workflow — Agent Rules -->
<!-- Add this to your AI coding tool's instruction file to enable -->
<!-- the Intent-First agentic workflow in your project -->
<!-- For tool-specific locations, see the install script or README -->

# Intent-First Agentic Workflow

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

```text
Intent → Spec → Plan → Execution → Artifacts
(human)  (agent) (agent)  (agent)     (agent)
         ↑ approval ↑ approval
```

**Every stage transition requires explicit human approval.**

### Stage Rules

**Intent** (human only):

- Never edit s1_intent.md as an agent
- Read it thoroughly before any work
- Ask clarifying questions if unclear (<70% confidence)

**Spec** (`/wf-spec <ID>`):

- Focus on WHAT and HOW (design), not implementation
- Include design decisions, public interfaces, quality gates
- Document deliverables and pass conditions
- Never proceed without human approval

**Plan** (`/wf-plan <ID>`):

- Must have approved, locked spec first
- Follow spec decisions strictly — 100% compliance
- Include all file paths, function signatures with types
- Detailed enough that no design decisions remain
- Never proceed without human approval

**Execution** (`/wf-execution <ID>`):

- Must have approved, locked plan first
- Follow plan exactly — any deviation needs human approval
- Update execution.md continuously (not batched)
- Document all issues and resolutions immediately

**Artifacts** (`/wf-artifacts <ID>`):

- Must have completed execution with all tests passing
- Document code changes, test results, design decisions
- Capture lessons learned
- Suggest follow-up work

### Critical Rules

1. **No auto-proceed**: Never move to next stage without human approval
2. **Stage locking**: Once approved and next stage begins, previous stage cannot be edited. Enforced via file permissions (read-only). Agents run `intent-first lock <ID> <stage>` automatically after approval.
3. **Confidence threshold**: If <70% confident at any point, stop and ask human. Use the scoring model below.
4. **Decision tracking**: All decisions must record datetime (UTC) and decision maker
5. **No reversal**: Locked stages are immutable. Create new workflow if major changes needed
6. **100% plan compliance**: During execution, any deviation requires documented human approval

### Confidence Scoring Model

When self-assessing confidence, score each category and sum for a 0–100 total.

Based on agentic calibration research (Zhang et al. 2026, Yang et al. 2026, Mao & Venkat 2026).

**Knowledge (0–35 pts)**

| Factor | Points | Criteria |
|--------|--------|----------|
| Pattern familiarity | 0–15 | 15 = exact known pattern, 10 = similar, 7 = partial, 3 = novel, 0 = unknown |
| Language/framework | 0–10 | 10 = current stable features, 7 = well-tested, 4 = quirky, 0 = deprecated/rare |
| Requirement clarity | 0–10 | 10 = explicit & complete, 7 = minor gaps, 4 = ambiguous, 0 = vague/conflicting |

**Complexity (0–30 pts)**

| Factor | Points | Criteria |
|--------|--------|----------|
| Reasoning steps | 0–10 | 10 = ≤2 steps, 7 = 3–4, 4 = 5–8, 2 = 9–15, 0 = >15 |
| Assumptions needed | 0–10 | 10 = none, 7 = 1–2, 4 = 3–5, 0 = >5 or high-risk |
| Codebase knowledge | 0–10 | 10 = familiar sections, 7 = 2–3 known areas, 4 = unfamiliar, 0 = unknown |

**Consistency (0–20 pts)**

| Factor | Points | Criteria |
|--------|--------|----------|
| Internal coherence | 0–10 | 10 = all approaches agree, 7 = minor variations, 3 = disagreements, 0 = contradictions |
| Track record | 0–10 | 10 = >95% on similar, 7 = 80–95%, 4 = 60–80%, 0 = <60% or none |

**Risk (0–15 pts)**

| Factor | Points | Criteria |
|--------|--------|----------|
| Edge case coverage | 0–15 | 15 = thorough, 10 = probable cases, 5 = incomplete, 0 = none considered |

**Score interpretation:**

- **85–100**: High — proceed normally
- **70–84**: Good — proceed, flag risky areas
- **55–69**: Moderate — test thoroughly, consider alternatives
- **40–54**: Low — ask human before proceeding
- **<40**: Stop — request clarification or break task down

**Calibration note:** LLMs systematically overestimate confidence by 10–30% (Tian et al. 2025). When in doubt, round down. For multi-step tasks, re-score after completing ~30% to catch compounding error.

### Creating a New Workflow

Run the CLI or manually create `workflow/<ID>/` with these files:

- `s1_intent.md` — Human-written goals (human only)
- `s2_spec.md` — Technical specification (agent drafts, human approves)
- `s3_plan.md` — Implementation plan (agent drafts, human approves)
- `s4_execution.md` — Progress tracking (agent updates continuously)
- `s5_artifacts.md` — Final outcomes (agent documents)

### Stage Prompts

Agents use these prompts to work on each stage:

- `/wf-spec <ID>` — Draft or improve specification
- `/wf-plan <ID>` — Create implementation plan
- `/wf-execution <ID>` — Execute plan with progress tracking
- `/wf-artifacts <ID>` — Document final outcomes
- `/wf-yolo <ID>` — Run all stages with auto-approval at ≥85% confidence

For detailed stage instructions, read the corresponding prompt file in the `prompts/` directory (or `.github/prompts/`, `.cursor/prompts/`, etc. depending on your tool).
