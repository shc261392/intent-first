# Why Not XXX?

Intent-First is a **superlightweight local agent enforcement protocol**. It's markdown files and a bash script. It runs locally, has zero dependencies, and works with any AI coding tool that reads markdown.

It is **not** a team collaboration tool, a project management platform, or an alternative to any workflow that involves multiple humans coordinating together. It enforces structure for a **single developer working with AI agents** on their local machine.

These 20 questions address the most common "why not just use X?" reactions. The answer is almost always: **they solve different problems.**

---

### 1. Why not just use Cursor Rules / Copilot Instructions directly?

Those give your agent *personality and constraints* but no *process*. The agent still decides what to do and in what order. Intent-First adds the missing layer: a stage-gated workflow where the agent can't skip design, can't skip planning, and can't proceed without your approval. They complement each other — Intent-First installs *into* those rule files.

### 2. Why not use Linear / Jira / GitHub Issues?

Those are team coordination tools for tracking work across people. Intent-First is a local protocol between you and your AI agent on your machine. There's no server, no ticket, no board. If you use Linear for your team, keep using it. Intent-First structures the part where you sit down with an AI agent and actually build the thing.

### 3. Why not just use Claude Code / Aider's architect mode?

Architect mode gives the agent freedom to design *and* build in one shot. That's great when it works. But for complex tasks, the agent makes architectural assumptions you never approved, and you discover them buried in a diff 500 lines later. Intent-First forces the architecture to be explicit, reviewed, and locked before a single line of code is written.

### 4. Why not just talk to the AI and iterate?

That works for small tasks. For anything substantial, you end up in a loop: the agent builds something wrong, you correct it, it rebuilds partly wrong, you correct again. Intent-First front-loads the thinking. By the time the agent writes code, it's following a plan you already approved — no iteration loop needed.

### 5. Why not use a proper spec document / RFC process?

RFC processes are designed for teams reviewing proposals asynchronously. Intent-First is a lightweight local version of that idea, streamlined for one developer and one AI agent working in real-time. If your organization has an RFC process, use it for team-level decisions. Use Intent-First for the implementation session afterward.

### 6. Why not use Notion / Confluence for documentation?

Those are knowledge management tools for teams. Intent-First workflow files are ephemeral — they exist during the build process and don't need to be stored permanently. They're like chat history: valuable in the moment, disposable after. If an outcome is worth preserving, commit it to your repo.

### 7. Why not just write better prompts?

Better prompts help. But a single prompt can't enforce a multi-stage process with approval gates and filesystem-level locking. Intent-First is the structure that makes your prompts work within a controlled workflow instead of a freeform conversation.

### 8. Why not use GitHub Projects / Kanban boards?

Those tools coordinate work streams across a team over time. Intent-First coordinates a single implementation session between you and an AI agent. Different scope, different purpose. Use your board to decide *what* to build. Use Intent-First to structure *how* you build it with your agent.

### 9. Why not use SpecKit / Antigravity for scaffolding?

Those help you start projects or generate boilerplate. Intent-First helps you build *every feature after that*. They're complementary. Scaffold your project with whatever tool you like, then use Intent-First for the ongoing work.

### 10. Why not just use git branches and PRs for review?

PRs are a review mechanism for finished work between humans. Intent-First operates *before* the code exists — it structures the design and planning that happens before your agent writes the first line. By the time you open a PR, the work has already been through spec, plan, and execution review.

### 11. Why not use AI-native IDEs that handle this automatically?

Current AI IDEs give you autocomplete, chat, and command execution. None of them enforce a stage-gated workflow where design is locked before planning, and planning is locked before execution. Intent-First adds that missing layer and works across *any* tool — it's not locked to one IDE.

### 12. Why not just trust the AI agent?

Because trust without verification is how you get subtle bugs in production. The 70% confidence threshold (based on a structured scoring model) exists because agents are confidently wrong more often than you'd expect — research shows LLMs overestimate confidence by 10–30%. Intent-First doesn't distrust the agent — it gives the agent a structure where it can be *verifiably* right at each stage.

### 13. Why not use Makefiles / task runners for workflow automation?

Task runners automate commands. Intent-First automates *decision-making structure*. A Makefile can't review a spec, enforce approval gates, or prevent an agent from skipping the planning stage. That said, you can absolutely wire `intent-first` commands into a Makefile if you want.

### 14. Why not use TDD — write tests first, then let the agent implement?

TDD tells the agent *what* the code should do but not *how* to design it. For complex features, the agent still needs architectural guidance. Intent-First and TDD work well together: the plan stage can include test cases, and execution tracks that tests pass.

### 15. Why not just use markdown files without the CLI?

You can! The CLI is optional convenience. It creates directories, copies templates, and manages file permissions for locking. If you'd rather do that manually, the workflow is just five markdown files in a folder. The protocol is the markdown; the CLI is a shortcut.

### 16. Why not use Slack / Discord for agent coordination?

Those are communication tools for humans. Intent-First coordinates locally between you and your AI agent through files on your filesystem. There's no messaging, no channels, no notifications. It's just structured files that your agent reads and writes.

### 17. Why not use a formal software design process (UML, TOGAF, etc.)?

Those are enterprise-grade processes for large teams building large systems. Intent-First is deliberately minimal — five markdown files and a bash script. It gives you just enough structure to keep an AI agent on track for a single feature, without the overhead of formal methodology.

### 18. Why not just review the git diff at the end?

By then the damage is done. If the agent made a wrong architectural decision in line 50, everything after it is potentially wrong too. Intent-First catches design problems *before* code is written. Reviewing a spec is faster than reviewing (and potentially reverting) a 500-line diff.

### 19. Why not use MCP servers or custom tool integrations?

MCP is a transport layer — it gives agents access to external tools. Intent-First is a workflow protocol that could theoretically *use* MCP for locking, but it doesn't need to. `chmod` works everywhere, on every OS, with every agent. No server, no configuration, no dependencies.

### 20. Why not build a VS Code extension / IDE plugin instead?

Because that locks you into one editor. Intent-First is primarily tested with VSCode GitHub Copilot extension and Copilot CLI, but works with Cursor, Claude Code in terminal, Aider in terminal, Windsurf, Cline, and Antigravity — all from the same set of markdown files. An extension would be a nice-to-have on top, but the protocol itself must remain tool-agnostic.

---

**Bottom line:** Intent-First isn't competing with team tools, project management platforms, or IDE features. It's a local enforcement protocol for the moment when one developer sits down with one AI agent and needs the agent to *think before it codes*. If you use Jira, Linear, GitHub Projects, or Notion — keep using them. Intent-First operates at a different layer.
