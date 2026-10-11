// Intent-First guard bridge for OpenCode. Installed by `intent-first init`; removed by `intent-first uninstall`.
// Runs .intent-first/guard.py before each tool call and blocks the call when the guard exits 2.
import { spawnSync } from "node:child_process"
import { existsSync } from "node:fs"
import { join } from "node:path"

export const IntentFirstGuard = async ({ worktree, directory }) => {
  const guard = join(worktree || directory, ".intent-first", "guard.py")
  return {
    "tool.execute.before": async (input, output) => {
      if (!existsSync(guard)) return
      const payload = JSON.stringify({ tool_name: input.tool, tool_input: output.args, cwd: directory })
      for (const python of ["python3", "python"]) {
        const result = spawnSync(python, [guard], { input: payload, encoding: "utf8", timeout: 10000 })
        if (result.error) continue
        if (result.status === 2) throw new Error((result.stderr || "").trim() || "[intent-first] blocked")
        return
      }
    },
  }
}
