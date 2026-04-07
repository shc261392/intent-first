# Intent-First Roadmap

## Current State (v2.0)

Intent-First is a lightweight local protocol using markdown files and a Python CLI. It currently works via:
- **Prompt files** placed in tool-specific directories (e.g., `.github/prompts/` for Copilot)
- **CLI commands** run in the terminal by agents (e.g., `intent-first lock`, `intent-first graph show`)
- **Rules file** injected into AI tool instruction configs

Primary support: **VSCode GitHub Copilot extension** and **GitHub Copilot CLI**.

---

## Research: VSCode Extension with Copilot Chat Integration

### Summary

**Feasibility: HIGH** — VSCode's Chat Participant API and Language Model Tool API provide the building blocks to turn Intent-First into a native Copilot Chat experience. The main question is not "can it be done" but "should the scope expand beyond the current lightweight protocol model."

### What a VSCode Extension Could Do

| Feature | Current (CLI + prompts) | Extension (Chat Participant) |
|---------|------------------------|------------------------------|
| Workflow commands | Agent runs `intent-first new` in terminal | User types `@intent-first /new add-auth` in Copilot Chat |
| Phase tracking | Agent calls `intent-first phase-update` | Extension auto-tracks phases as chat progresses |
| Status display | `intent-first status --workflow 1` in terminal | Sidebar panel with live stage/phase/graph visualization |
| Execution graph | ASCII art in terminal | Interactive DAG visualization (webview) |
| Stage locking | `chmod` via CLI | Extension manages locks + shows lock status in editor gutter |
| Approval flow | Agent uses `askQuestion`, user types response | Structured approve/reject buttons in chat UI |
| YOLO mode | Separate prompt file | Chat command: `@intent-first /yolo add-auth` |

### Technical Architecture

#### Chat Participant API
- Register `@intent-first` as a [Chat Participant](https://code.visualstudio.com/api/extension-guides/ai/chat) in Copilot Chat
- Slash commands map to workflow stages: `/spec`, `/plan`, `/execute`, `/artifacts`, `/yolo`
- The participant wraps the existing workflow prompts as system instructions and injects context (status.yml, execution-graph.json) into the LLM conversation
- Responses stream back through the Chat API with markdown rendering

#### Language Model Tool API
- Register [LM Tools](https://code.visualstudio.com/api/extension-guides/ai/tools) via `vscode.lm.registerTool()` that the model can call:
  - `intent-first.newWorkflow` — create workflow directory and files
  - `intent-first.lockStage` — lock a stage file (chmod + status update)
  - `intent-first.updatePhase` — update phase status in status.yml
  - `intent-first.graphUpdate` — update execution graph node status
  - `intent-first.readStatus` — read workflow status for context
  - `intent-first.configure` — get/set user preferences
- Tools declared in `package.json` with JSON Schema input definitions
- The LLM calls these tools automatically during conversation, replacing manual terminal commands

#### Sidebar / Webview Panel
- Tree view showing all workflows with status indicators
- Clicking a workflow opens a detailed view:
  - Stage progression bar (Intent ✅ → Spec ✅ → Plan ⏳ → ...)
  - Phase breakdown for current stage
  - Interactive execution graph (D3.js or simple SVG)
- Real-time updates via file watchers on `status.yml` and `execution-graph.json`

#### File System Integration
- Editor decorations showing lock status (🔒 icon in gutter for locked stages)
- CodeLens on stage files: "Approve & Lock" / "View Status" actions
- File watcher triggers status panel refresh when agents modify status.yml

### Key Dependencies & APIs

| API | Purpose | Stability |
|-----|---------|-----------|
| `vscode.chat.createChatParticipant()` | Register `@intent-first` participant | Stable (GA since VS Code 1.93+) |
| `vscode.lm.registerTool()` | Register callable tools for LLM | Stable (GA since VS Code 1.99+) |
| `vscode.window.createWebviewPanel()` | DAG visualization sidebar | Stable |
| `vscode.workspace.createFileSystemWatcher()` | Watch status.yml changes | Stable |
| `@vscode/chat-extension-utils` | Simplify chat participant boilerplate | Community library, maintained by Microsoft |

### Constraints & Risks

1. **Copilot subscription required** — Chat Participant API requires GitHub Copilot to be active. Users without Copilot can't use the chat interface (but CLI still works).

2. **Terminal access limitations** — The LM Tool API can send commands to the terminal (`terminal.sendText()`), but reading terminal output back is limited and experimental. For intent-first this is fine since we use file-based state (status.yml, execution-graph.json) rather than terminal output.

3. **Model dependency** — Chat participants can choose models via `vscode.lm.selectChatModels()`, but the available models depend on the user's Copilot plan. The extension should work with any model Copilot offers.

4. **Extension size** — Adding a TypeScript extension adds a build step and `node_modules`. This conflicts with the "zero dependencies" philosophy. Mitigation: the extension would be a separate optional package, the CLI remains the core.

5. **Maintenance burden** — VSCode APIs evolve fast. The extension needs to track API changes across VS Code versions. The current prompt-file approach is more resilient to API churn.

6. **Cross-tool support** — A VSCode extension only helps VSCode users. Cursor, Claude Code, Windsurf users would still need the CLI + prompt file approach.

### Recommended Approach: Incremental

Rather than a full rewrite, build the extension as an **optional enhancement layer** on top of the existing CLI:

**Phase A: Basic Extension (estimated: 2-3 weeks)**
- Chat participant `@intent-first` with slash commands (`/new`, `/spec`, `/plan`, `/execute`, `/artifacts`, `/yolo`)
- Wraps existing prompt content as system instructions
- Calls CLI commands via `child_process.exec()` for state mutations (lock, status-update, etc.)
- Simple tree view sidebar showing workflow list and status

**Phase B: Native Tools (estimated: 2-3 weeks)**
- Register LM Tools replacing CLI calls with direct file operations
- Status panel with phase breakdown
- File watchers for live updates
- CodeLens integration on stage files

**Phase C: Rich Visualization (estimated: 2-4 weeks)**
- Webview-based execution graph visualization
- Interactive approval flow (approve/reject buttons in chat)
- Drag-and-drop graph editing in plan stage
- Settings UI for `intent-first configure`

### Decision

**Recommendation: Proceed with Phase A as a separate `intent-first-vscode` repository.**

Rationale:
- Low risk — the extension wraps existing CLI, doesn't replace it
- Validates the UX before investing in deeper integration
- Keeps the core project lightweight and tool-agnostic
- Can be published to VS Code Marketplace independently
- Users who don't want the extension continue using prompt files + CLI

---

## Other Roadmap Items

### Short-Term (v2.x)

- [ ] **Workflow templates** — pre-built intent templates for common patterns (add API endpoint, refactor module, add tests)
- [ ] **Export/import** — export a completed workflow as a shareable report
- [ ] **Audit log** — persistent log of all agent decisions and approvals across workflows

### Medium-Term (v3.0)

- [ ] **VSCode extension Phase A** — basic `@intent-first` chat participant (see research above)
- [ ] **Multi-agent execution** — parallel node execution when agent supports sub-agents
- [ ] **Workflow analytics** — track time-per-stage, approval rates, common deviation patterns

### Long-Term

- [ ] **VSCode extension Phase B+C** — native tools, rich visualization
- [ ] **GitHub App integration** — trigger workflows from issues/PRs
- [ ] **Team workflows** — shared workflow state via git (opt-in, not default)

---

## References

- [VSCode Chat Participant API](https://code.visualstudio.com/api/extension-guides/ai/chat)
- [VSCode Language Model Tool API](https://code.visualstudio.com/api/extension-guides/ai/tools)
- [Chat Participant Tutorial](https://code.visualstudio.com/api/extension-guides/ai/chat-tutorial)
- [chat-sample extension](https://github.com/microsoft/vscode-extension-samples/tree/main/chat-sample)
- [@vscode/chat-extension-utils](https://github.com/microsoft/vscode-chat-extension-utils)
