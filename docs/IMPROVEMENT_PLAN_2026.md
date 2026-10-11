# Intent-First 改善計畫（2026 SOTA 對照版）

> 目標：讓 Intent-First 成為**真正實用的 lightweight、pluggable 協定**。
> 意思是：30 秒裝上、對每個主流 agent 都用「原生」的方式載入、強制力來自 harness 而非提示詞、拔掉時不留痕跡。

## 決策與執行狀態（v3.0.0）

Maintainer 決策：**License 改 MIT**、**接受破壞性變更**、**一級支援 Copilot / Claude Code / Cursor / Codex / OpenCode 五個工具**。

| 項目 | 狀態 | 實作位置 |
|---|---|---|
| P0.1 CI 跑單元測試（Linux/macOS/Windows × Py3.9/3.13）、刪除 `__pycache__` | ✅ | `.github/workflows/ci.yml`、`tests/` |
| P0.2 各工具安裝路徑修正 | ✅ | `src/intent_first/adapters.py` |
| P0.3 `AGENTS.md` 支援 | ✅ | `assets/agents-block.md` |
| P0.4 版本釘選 + SHA-256 + attestation | ✅ | `install.sh`、`.github/workflows/release.yml` |
| P0.5 文件誠實化、移除寫死模型 | ✅ | `README.md`、`WHY_NOT_XXX.md` |
| P1.1 `PROTOCOL.md` + `state.schema.json` + `migrate` | ✅ | `spec/`、`intent-first migrate` |
| P1.2 Agent Skills 改寫（常駐 ≈110 字、全部 skill ≈1.9k 字，原 ≈7.5k 字） | ✅ | `assets/skills/` |
| P1.3 由單一來源產生各工具格式 | ✅（改為 `init` 時產生，不需 build 步驟） | `adapters.py` |
| P1.4 Hook 強制 | ✅ 五個工具皆有 | `guard.py` |
| P1.5 Plugin / marketplace 包裝 | ⏳ 後續 | — |
| P1.6 `approve` + Open Questions gate、移除 confidence 打分 | ✅ | `state.py`、`intent-first check` |
| P1.7 套件化（wheel/sdist/zipapp，`uvx` 可用） | ✅；PyPI 發佈待 maintainer 設定 trusted publishing | `pyproject.toml`、`scripts/build_pyz.py` |
| P2.1 真實模型行為 eval | ⏳ 後續 | — |
| P2.2 阻擋事件 audit log | ✅ | `.intent-first/audit.log` |
| P3 MCP server、export | ⏳ 後續 | — |

### Stage 設計修訂（v3.0.0 發佈前）

| 原設計 | 問題 | 新設計 |
|---|---|---|
| Artifacts 是第 5 個 stage | 交付紀錄很重要，但讓 agent 另寫一份文件、再審一次，成本高，內容也會偏離實際 | 刪除該 stage。執行核准時由 CLI 從追溯鏈**產生** `report.md`（目標 → 驗收條件 → 工作 → 結果、偏差、後續工作、diff stat），不耗 token、不會失真 |
| Intent mapping 是 spec 裡的一個 phase | 對應關係寫在文字裡，無法檢查 | 改成**貫穿各階段的 ID 追溯鏈**：`G1` → `AC1 (G1)` → node `--covers AC1` + Verification → `AC1: pass — 證據`。每個 gate 由 `check` 驗證鏈結完整 |
| Spec 與 plan 都寫「設計」，界線模糊 | 兩份文件重複，agent 在 plan 做新決策 | **Spec = 外部視角的 what/why**（行為、介面、決策、驗收條件），讀者是決定「該不該做」的人。**Plan = 內部視角的 how/順序**（檔案、步驟、測試、驗證），讀者是執行的 agent，不得新增行為或決策。`check` 會提示 spec 中的檔案路徑，並要求 plan 每個 node 都服務某個驗收條件、步驟與 node 一一對應 |

已知限制：
- Codex 的 project hook 需在 `/hooks` 信任一次；社群回報部分版本對 `apply_patch` 的 deny 未生效（openai/codex#27833），此時仍有檔案唯讀與 hash 檢查作為後援。
- Shell 指令的寫入偵測是啟發式（重導向、`rm`、`mv`、`sed -i` 等），無法涵蓋所有寫法；`intent-first check` 的 hash 比對會抓到漏網的修改。
- 同時選 Claude 與其他工具時，`.claude/skills/` 與 `.agents/skills/` 內容相同；Copilot/Cursor/OpenCode 兩處都讀，以同名 skill 呈現。

---

---

## 0. TL;DR

| 面向 | 現況（v2.0） | 2026 SOTA 該有的樣子 | 優先級 |
|---|---|---|---|
| 載入方式 | 把 prompt 檔複製到各工具目錄，多數路徑已不正確（如 `.claude/prompts`） | 以 **Agent Skills（`SKILL.md`）** 為單一來源，加上 **`AGENTS.md`** 一行指引；Claude Code / Copilot CLI 再提供 **plugin** 包裝 | P0 |
| 強制力 | `chmod` + 提示詞要求 agent 自己去 lock | **Hooks**（PreToolUse / pre-write）在 harness 層阻擋對已鎖定 stage 的寫入與越級操作 | P0 |
| 狀態 | `status.yml` 用 regex 讀寫、無 schema | `state.json` + JSON Schema，CLI 是唯一寫入者；可選 MCP server 暴露同一組操作 | P1 |
| 發佈／供應鏈 | `curl \| bash` 從 `main` 抓檔，無版本釘選、無校驗 | 版本化 release + SHA-256 + artifact attestation；`uvx` / `pipx` / plugin marketplace 安裝 | P0 |
| Context 成本 | 規則 + prompts ≈ 7.5k 英文字，多數每次都載入 | Progressive disclosure：常駐 < 300 tokens，stage 指令按需載入 | P1 |
| 評測 | promptfoo `echo` provider 只做字串比對；78 個 unittest 未在 CI 執行 | 結構 lint + CI 跑單元測試 + 少量真實 agent trajectory eval | P0/P2 |
| 可攜性 | prompts 寫死 Copilot 專屬工具名（`vscode/askQuestions`、`#tool:`） | 工具中立的指令；工具差異只存在 adapter 的 frontmatter | P1 |

---

## 1. 現況診斷（有證據的問題）

### 1.1 Pluggability：安裝到的位置與現行工具慣例不符
`cli/intent-first:65-100` 的 `TOOL_PROMPT_DIRS` / `_TOOL_DIRS`：

- **Claude Code**：`.claude/prompts/` 不是任何會被讀取的位置。現行是 `.claude/skills/<name>/SKILL.md`（slash command 已併入 skills）與 `.claude/agents/*.md`；agent 檔的 frontmatter 格式與 Copilot 不同（`tools` 名稱不同、無 `argument-hint`）。
- **Cursor**：規則是 `.cursor/rules/*.mdc`（含 `description`/`globs`/`alwaysApply`），指令是 `.cursor/commands/`；`.cursor/prompts/` 不會被讀。
- **Windsurf**：`.windsurf/rules/` 與 `.windsurf/workflows/`；`.windsurfrules` 已是舊格式。
- **Cline**：`.clinerules/` 是目錄。
- **Codex / Gemini CLI / Jules / Amp 等**：完全沒覆蓋，但它們都讀 `AGENTS.md`（或可設定讀它）。
- 結果：README 宣稱支援 7 個工具，實際上只有 Copilot 真正可用。

### 1.2 Enforcement 只靠「請 agent 自律」
- 鎖定由 prompt 要求 agent 跑 `intent-first lock`（`README.md` Stage Locking 一節）；`unlock` 同樣可被 agent 呼叫。
- 「70% confidence 打分」（`rules/RULES.md:85-126`）是 LLM 自評，已知校準不佳；它無法被驗證，也無法被 harness 執行。
- 2026 主流 agent（Claude Code、Copilot CLI / coding agent、Cursor、Codex、Gemini CLI）都有 **hooks**，可以在工具呼叫前以 exit code 阻擋——這才是「enforcement protocol」該依附的層。

### 1.3 狀態管理脆弱
- `status.yml` 以 regex 解析與改寫（`cli/intent-first:280-317, 347-400, 596-660`），依賴固定縮排；人或 agent 手改一次格式就可能 silent fail（`update_stage_field` 在檔案不可寫時直接 `return`）。
- `execution-graph.json` 與 `status.yml` 兩份狀態並存，沒有 schema，`validate` 無法給出可機讀的錯誤。

### 1.4 供應鏈與版本
- `install.sh` 與 `cmd_upgrade` 都從 `raw.githubusercontent.com/.../main` 下載（`cli/intent-first:22`、`install.sh:11`），**但** `upgrade` 用的是 `releases/latest` 的 tag 做比較 → 會把 `main` 上未發佈的 CLI 當成「最新版」裝上。
- 無 checksum、無簽章、`curl | bash` 會改寫 shell profile。

### 1.5 「Lightweight」名不符實
- README / WHY_NOT_XXX 反覆說「markdown + bash script、zero dependencies」，但核心是 2,045 行單檔 Python。（Python 3 stdlib 依賴本身沒問題，問題是文件不誠實。）
- 規則與 prompts 合計 ~7.5k 英文字、強制文法（`MUST`、`FORBIDDEN`、`Zero tolerance`）大量重複；新一代模型對過度強調會過度反應（例如把所有事都升級成問使用者）。
- `status.yml` 預先列出 17 個 phase，每個 stage 都要求 agent 呼叫 `phase-update`，工具呼叫次數與 context 開銷高。

### 1.6 品質保證
- `.github/workflows/test.yml` 只測 `install.sh` 與幾個 CLI 指令；`tests/` 內 78 個 unittest（本地 44s 全過）**沒有在 CI 執行**。
- `promptfooconfig.yaml` 用 `echo` provider，只檢查字串存在——不是行為評測。
- `tests/__pycache__/*.pyc` 被 commit 進 repo。
- `agents/wf-auditor.agents.md` 寫死 `Claude Haiku 4.5` / `Gemini 3 Flash (Preview)`，過時且不可攜。

### 1.7 其他
- License 為 GPL-3.0：對「被植入使用者 repo 的設定檔與 prompts」而言，會讓公司用戶卻步。是否改 MIT / Apache-2.0 由 maintainer 決定（見 §6）。

---

## 2. 2026 SOTA 參考標準

| 標準／機制 | 用途 | Intent-First 怎麼用 |
|---|---|---|
| **`AGENTS.md`**（跨工具開放格式，Codex、Copilot、Cursor、Jules、Amp、Gemini CLI 等支援） | 常駐專案指引 | 只放 1–3 行：「多檔案功能請走 intent-first skill；`.intent-first/` 下已鎖定檔案不可修改」 |
| **Agent Skills（`SKILL.md`，開放規格）** | 按需載入的能力包，frontmatter 只有 `name` + `description` 常駐 | 每個 stage 一個 skill；canonical 來源，其他格式由它生成 |
| **Plugins / marketplace**（Claude Code、Copilot CLI） | 一次打包 skills + agents + hooks + MCP | `/plugin install intent-first` 即用，拔除即乾淨 |
| **Hooks**（PreToolUse、UserPromptSubmit、Stop 等） | Harness 層的確定性控制 | 阻擋寫入已鎖定 stage、阻擋未核准就進下一 stage、Stop 時檢查 deliverable |
| **MCP（2025-11 規格）** | 結構化工具 | 可選：`intent_first.status / approve / lock / graph_*`，取代解析 terminal 輸出 |
| **Subagents** | 隔離 context 的審查者 | Auditor 改為工具中立的 subagent 定義，不寫死模型 |
| **供應鏈**：GitHub artifact attestations、Sigstore、`uv tool` | 可驗證安裝 | release 資產附 SHA-256 與 attestation |

設計原則：**Protocol 是 markdown + JSON schema；enforcement 交給 harness；工具差異只留在 adapter。**

---

## 3. 目標架構

```
intent-first/
├── spec/                         # 工具中立的「協定」本體（唯一真相）
│   ├── PROTOCOL.md               # 5 stage、gate、狀態機（≤ 1 頁）
│   └── state.schema.json         # .intent-first/workflows/<id>/state.json 的 schema
├── skills/                       # canonical：Agent Skills 格式
│   ├── intent-first/SKILL.md     # 入口：何時使用、如何開新 workflow
│   ├── if-spec/SKILL.md
│   ├── if-plan/SKILL.md
│   ├── if-execute/SKILL.md
│   ├── if-artifacts/SKILL.md
│   └── if-auditor/…              # subagent 定義
├── hooks/
│   └── guard.py                  # 單一 hook 程式，stdin 讀事件 JSON，exit 2 阻擋
├── adapters/                     # 由 build 腳本從 skills/ 生成，不手寫
│   ├── claude-code/              # .claude-plugin/plugin.json + hooks.json
│   ├── copilot/                  # .github/prompts、.github/agents、hooks
│   ├── cursor/                   # .cursor/rules/*.mdc、.cursor/commands/
│   ├── windsurf/ cline/ codex/ gemini/ …
├── mcp/ (optional)               # stdio MCP server，重用 CLI 核心
└── src/intent_first/             # CLI 拆模組：state、graph、install、adapters
```

### 3.1 狀態模型（取代 `status.yml` + `execution-graph.json`）
- 單一 `state.json`，由 `state.schema.json` 驗證；CLI / MCP 是唯一寫入者，寫入採 atomic replace。
- Stage 狀態機：`pending → draft → approved → locked`；approve 需記錄 `approved_by`（取自 `git config user.name` 或 `configure`）與 UTC 時間。
- Phase 改為**可選**的進度標記，不再強制 agent 每步呼叫；`validate` 以 deliverable 內容（必備章節）判定完成度。
- 每個 locked stage 記錄 `sha256`，`validate` 偵測鎖定後被改動（比 `chmod` 更可靠，且跨平台含 Windows）。

### 3.2 Enforcement 分層（從強到弱，各工具取其所能）
1. **Hook（確定性）**：`guard.py` 在寫檔工具呼叫前檢查目標路徑；若屬於 locked stage 或越級（plan 未 approved 卻寫 `s4_execution.md`）→ 阻擋並回傳原因給 agent。`intent-first unlock` 只允許人類從 terminal 執行（hook 阻擋 agent 呼叫 `unlock`）。
2. **Hash 驗證**：`intent-first validate` / Stop hook 比對 sha256。
3. **檔案權限**：保留 `chmod` 作為無 hook 工具的退路。
4. **提示詞**：最後一層，而非唯一一層。

### 3.3 「Approval」改由人類動作產生
- `intent-first approve <id> <stage>`（人類在 terminal 跑，或在支援的工具中透過 `AskUserQuestion` 類工具確認後由 hook 記錄 `UserPromptSubmit` 的明確核准字串）。
- 移除 LLM 自評 70%/85% 分數；改為 deliverable 內必填 **Open Questions / Assumptions** 區塊——有未解問題就不能請求核准。YOLO 模式改為「無 Open Questions 時自動核准」，可稽核且可測試。

---

## 4. 分階段 Roadmap

### P0 — 修正可用性與信任（1–2 週，v2.1，無破壞性變更）
| # | 工作 | 驗收標準 |
|---|---|---|
| 0.1 | CI 執行 `python -m unittest`（ubuntu/macos/windows，Python 3.9–3.13） | PR 上可見綠燈；刪除 committed `__pycache__` |
| 0.2 | 修正各工具安裝路徑（Claude → `.claude/skills` + `.claude/agents`；Cursor → `.mdc` + `commands`；Windsurf → `rules/` + `workflows/`；Cline → `.clinerules/`） | 每個 adapter 有一個 fixture test 斷言產出路徑與 frontmatter |
| 0.3 | 新增 `AGENTS.md` 支援（`init --tool agents-md`，預設也寫入） | Codex / Gemini CLI 可在 fresh repo 中找到指引 |
| 0.4 | 版本釘選：`install.sh` 與 `upgrade` 下載**同一 release tag** 的檔案，校驗 `SHA256SUMS`；release workflow 產生 attestation | `upgrade` 不再取用 `main` |
| 0.5 | 文件誠實化：「Python 3 stdlib，零第三方依賴」；移除寫死的模型名 | README / WHY_NOT_XXX 與實作一致 |

### P1 — 協定與 adapter 重構（2–4 週，v3.0，破壞性變更附 migration）
| # | 工作 | 驗收標準 |
|---|---|---|
| 1.1 | `spec/PROTOCOL.md` + `state.schema.json`；CLI 改讀寫 `state.json`，提供 `intent-first migrate` 從 v2 `status.yml` 轉換 | 既有 78 測試改寫後全過；migrate 有 round-trip 測試 |
| 1.2 | Prompts 改寫為 `skills/*/SKILL.md`：工具中立、去重、常駐 frontmatter < 300 tokens、單一 stage 指令 < 1.5k tokens | `scripts/lint_skills.py` 檢查 frontmatter、token 預算、禁止工具專屬名稱 |
| 1.3 | `scripts/build_adapters.py` 由 skills 生成各工具格式；CI 檢查生成物無 diff | 新增一個工具 = 新增一個 adapter 函式 + fixture |
| 1.4 | `hooks/guard.py` + Claude Code / Copilot hook 設定 | e2e 測試：模擬 hook 事件 JSON，對 locked 檔案寫入回傳 exit 2 |
| 1.5 | Claude Code plugin 與 Copilot CLI plugin manifest；repo 本身即 marketplace | `/plugin marketplace add shc261392/intent-first` 可安裝 |
| 1.6 | `approve` 指令 + Open Questions gate，移除 confidence 打分 | YOLO 行為有單元測試 |
| 1.7 | CLI 拆成 `src/intent_first/` 套件，發佈到 PyPI；仍保留單檔 zipapp 供 `curl` 安裝 | `uvx intent-first init` 可用 |

### P2 — 可量測的品質（2 週）
| # | 工作 | 驗收標準 |
|---|---|---|
| 2.1 | 以 promptfoo（或同等工具）用真實模型跑**行為** eval：給固定 fixture repo + intent，斷言 agent 沒有在 spec 階段改程式碼、有寫 Open Questions、沒有寫入 locked 檔 | nightly / 手動觸發，結果存成 artifact |
| 2.2 | Hook 阻擋事件寫入 `.intent-first/audit.log`（JSONL） | `intent-first status` 顯示被阻擋次數 |
| 2.3 | 用 eval 比較「完整 5 stage」vs「精簡 3 stage（spec+plan 合併）」在中小型任務上的成本/成功率，資料驅動決定是否簡化 | 結論寫入 docs |

### P3 — 選配擴充（依需求）
- `mcp/`：stdio MCP server，重用 CLI 核心；適合沒有 hook 但支援 MCP 的工具。
- `intent-first export <id>`：輸出單一 markdown 報告，可貼到 PR description（取代「全部 gitignore」造成的資訊流失）。
- 原 Roadmap 的 VS Code extension：在 skills + hooks + MCP 完成後，價值大幅下降，建議**降級為不做**，除非有明確使用者需求。

---

## 5. 刻意不做（保持 lightweight）
- 不做 server、DB、dashboard、team 同步。
- 不引入第三方 Python 依賴（schema 驗證用 stdlib 手寫最小 validator 即可）。
- 不為每個工具手寫 prompt——只維護 `skills/` 一份。
- 不追求對 agent 的「零信任」：hook 是安全帶，不是沙箱；README 保留這個定位。

---

## 6. Maintainer 決策（已定案）
1. **License**：改為 MIT。✅
2. **破壞性變更**：接受。提供 `intent-first migrate`（v2 → v3）。✅
3. **一級支援工具**：Copilot、Claude Code、Cursor、Codex、OpenCode。✅
4. **Stage 數量**：待 P2 eval 後再決定是否提供精簡模式。

---

## 7. 建議的第一個 PR
P0.1 + P0.2 + P0.5：CI 跑既有測試、修正安裝路徑、文件誠實化。改動小、無破壞性，能立刻讓 README 的「支援 7 個工具」從宣稱變成事實。
