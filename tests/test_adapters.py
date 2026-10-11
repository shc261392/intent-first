"""init / re-init / uninstall for the five supported agents."""

from __future__ import annotations

import json
import unittest

from helpers import ProjectTestCase
from intent_first import adapters

EXPECTED = {
    "claude": [".claude/skills/intent-spec/SKILL.md", ".claude/settings.json", "CLAUDE.md"],
    "copilot": [".github/hooks/intent-first.json"],
    "cursor": [".cursor/hooks.json"],
    "codex": [".codex/hooks.json"],
    "opencode": [".opencode/plugins/intent-first.js", ".opencode/commands/intent-spec.md"],
}
COMMON = ["AGENTS.md", ".gitignore", ".agents/skills/intent-first/SKILL.md", ".intent-first/guard.py",
          ".intent-first/config.json", ".intent-first/manifest.json"]


class InitTest(ProjectTestCase):
    def test_each_tool_alone(self):
        for tool, files in EXPECTED.items():
            with self.subTest(tool=tool):
                self.run_cli("init", "--tools", tool)
                for rel in COMMON + files:
                    self.assertTrue((self.root / rel).exists(), rel)
                others = [f for t, fs in EXPECTED.items() if t != tool for f in fs]
                for rel in others:
                    self.assertFalse((self.root / rel).exists(), f"{rel} should not exist for {tool}")
                for rel in files:
                    if rel.endswith(".json"):
                        data = json.loads((self.root / rel).read_text())
                        self.assertIn(adapters.GUARD_MARK, json.dumps(data))

    def test_hook_config_shapes(self):
        self.run_cli("init", "--tools", "all")
        claude = json.loads((self.root / ".claude/settings.json").read_text())
        self.assertEqual(claude["hooks"]["PreToolUse"][0]["matcher"], adapters.CLAUDE_MATCHER)
        copilot = json.loads((self.root / ".github/hooks/intent-first.json").read_text())
        self.assertEqual(copilot["version"], 1)
        self.assertIn("bash", copilot["hooks"]["PreToolUse"][0])
        cursor = json.loads((self.root / ".cursor/hooks.json").read_text())
        self.assertEqual(cursor["version"], 1)
        self.assertEqual(set(cursor["hooks"]), {"preToolUse", "beforeShellExecution"})
        codex = json.loads((self.root / ".codex/hooks.json").read_text())
        self.assertIn("apply_patch", codex["hooks"]["PreToolUse"][0]["matcher"])

    def test_reinit_is_idempotent_and_drops_deselected_tools(self):
        self.run_cli("init", "--tools", "claude,cursor")
        self.run_cli("init", "--tools", "claude,cursor")
        settings = json.loads((self.root / ".claude/settings.json").read_text())
        self.assertEqual(len(settings["hooks"]["PreToolUse"]), 1)
        self.assertEqual((self.root / "AGENTS.md").read_text().count(adapters.MD_BEGIN), 1)
        self.assertEqual((self.root / ".gitignore").read_text().count(adapters.GI_BEGIN), 1)
        self.run_cli("init", "--tools", "claude")
        self.assertFalse((self.root / ".cursor").exists())
        self.run_cli("init")  # reuses the manifest's tool list
        self.assertEqual(adapters.installed_tools(self.root), ["claude"])

    def test_detection(self):
        (self.root / ".cursor").mkdir()
        (self.root / "CLAUDE.md").write_text("# mine\n")
        self.assertEqual(adapters.detect_tools(self.root), ["claude", "cursor"])
        self.assertIn("tools: claude, cursor", self.run_cli("init"))

    def test_unknown_tool(self):
        self.assertIn("Unknown tool", self.run_cli("init", "--tools", "windsurf", expect=1))

    def test_foreign_file_is_not_overwritten(self):
        target = self.root / ".github/hooks/intent-first.json"
        target.parent.mkdir(parents=True)
        target.write_text('{"mine": true}\n')
        out = self.run_cli("init", "--tools", "copilot")
        self.assertIn("not created by intent-first", out)
        self.assertEqual(target.read_text(), '{"mine": true}\n')

    def test_invalid_json_is_left_alone(self):
        (self.root / ".cursor").mkdir()
        (self.root / ".cursor/hooks.json").write_text("{ // jsonc\n}")
        self.assertIn("not plain JSON", self.run_cli("init", "--tools", "cursor"))
        self.assertEqual((self.root / ".cursor/hooks.json").read_text(), "{ // jsonc\n}")


class UninstallTest(ProjectTestCase):
    def test_round_trip_preserves_user_content(self):
        (self.root / "CLAUDE.md").write_text("# My project\nKeep me.\n")
        (self.root / ".gitignore").write_text("node_modules/\n")
        (self.root / ".claude").mkdir()
        user_settings = {"permissions": {"allow": ["Bash(ls)"]},
                         "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo mine"}]}]}}
        (self.root / ".claude/settings.json").write_text(json.dumps(user_settings))
        self.run_cli("init", "--tools", "all")
        self.run_cli("new", "w")
        self.run_cli("uninstall", "--yes")
        self.assertEqual((self.root / "CLAUDE.md").read_text(), "# My project\nKeep me.\n")
        self.assertEqual((self.root / ".gitignore").read_text(), "node_modules/\n")
        self.assertEqual(json.loads((self.root / ".claude/settings.json").read_text()), user_settings)
        for rel in ("AGENTS.md", ".agents", ".github", ".cursor", ".codex", ".opencode", ".claude/skills",
                    ".intent-first/guard.py", ".intent-first/manifest.json"):
            self.assertFalse((self.root / rel).exists(), rel)
        self.assertTrue(self.wf_path("w", "state.json").exists())

    def test_purge_removes_everything_even_locked_files(self):
        self.run_cli("init", "--tools", "codex")
        self.run_cli("new", "w")
        self.write_stage("w", "intent", "# I\n\n## Goals\n- G1: x\n")
        self.run_cli("approve", "w")
        self.run_cli("uninstall", "--yes", "--purge")
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [".git"])

    def test_doctor(self):
        self.run_cli("doctor", expect=1)
        self.run_cli("init", "--tools", "copilot")
        self.assertIn("guard blocks", self.run_cli("doctor"))
        (self.root / ".github/hooks/intent-first.json").unlink()
        self.assertIn("missing", self.run_cli("doctor", expect=1))


if __name__ == "__main__":
    unittest.main()
