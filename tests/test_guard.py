"""The pre-tool-use guard, fed the payload shapes each supported agent sends."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

from helpers import GOOD, SRC, ProjectTestCase, add_nodes
from intent_first import adapters, guard

WF = ".intent-first/workflows/w"


class GuardTest(ProjectTestCase):
    def setUp(self):
        super().setUp()
        self.run_cli("init", "--tools", "all")
        self.run_cli("new", "w")
        self.write_stage("w", "intent", GOOD["intent"])
        self.run_cli("approve", "w")

    def decide(self, payload: dict) -> str | None:
        payload.setdefault("cwd", str(self.root))
        return guard.decide(payload, self.root)

    # -- payload shapes per tool --
    def test_claude_and_copilot_pascal_case(self):
        self.assertIn("approved and locked", self.decide({"tool_name": "Write", "tool_input": {"file_path": f"{WF}/intent.md"}}))
        self.assertIsNone(self.decide({"tool_name": "Edit", "tool_input": {"file_path": f"{WF}/spec.md"}}))
        self.assertIn("waits for spec approval", self.decide({"tool_name": "MultiEdit", "tool_input": {"file_path": f"{WF}/plan.md"}}))
        self.assertIn("managed by the intent-first CLI", self.decide({"tool_name": "Write", "tool_input": {"file_path": f"{WF}/state.json"}}))
        self.assertIsNone(self.decide({"tool_name": "Read", "tool_input": {"file_path": f"{WF}/intent.md"}}))
        self.assertIn("generated", self.decide({"tool_name": "Write", "tool_input": {"file_path": f"{WF}/report.md"}}))
        self.assertIsNone(self.decide({"tool_name": "Write", "tool_input": {"file_path": f"{WF}/artifacts.md"}}))

    def test_copilot_camel_case_with_json_string_args(self):
        payload = {"toolName": "edit", "toolArgs": json.dumps({"path": str(self.root / "src/app.py")})}
        self.assertIn("plan is approved", self.decide(payload))
        self.assertIsNone(self.decide({"toolName": "view", "toolArgs": json.dumps({"path": "src/app.py"})}))

    def test_cursor_shell_and_tool_events(self):
        self.assertIn("reserved for the human", self.decide({"command": "intent-first deactivate"}))
        self.assertIsNone(self.decide({"command": "ls -la"}))
        self.assertIn("plan is approved", self.decide({"tool_name": "StrReplace", "tool_input": {"path": "a.py"}}))

    def test_codex_apply_patch(self):
        patch = "*** Begin Patch\n*** Update File: src/app.py\n@@\n-a\n+b\n*** End Patch\n"
        self.assertIn("plan is approved", self.decide({"tool_name": "apply_patch", "tool_input": {"command": patch}}))
        patch = f"*** Begin Patch\n*** Add File: {WF}/spec.md\n+hi\n*** End Patch\n"
        self.assertIsNone(self.decide({"tool_name": "apply_patch", "tool_input": {"command": patch}}))
        self.assertIn("reserved", self.decide({"tool_name": "Bash", "tool_input": {"command": ["bash", "-lc", "intent-first reopen w intent"]}}))

    def test_opencode_shapes(self):
        self.assertIn("approved and locked", self.decide({"tool_name": "write", "tool_input": {"filePath": f"{WF}/intent.md"}}))
        self.assertIn("reserved", self.decide({"tool_name": "bash", "tool_input": {"command": "intent-first uninstall -y"}}))

    # -- rules --
    def test_code_edits_allowed_after_plan_or_when_inactive(self):
        edit = {"tool_name": "Write", "tool_input": {"file_path": "src/app.py"}}
        self.assertIsNotNone(self.decide(dict(edit)))
        self.run_cli("deactivate")
        self.assertIsNone(self.decide(dict(edit)))
        self.run_cli("activate", "w")
        self.run_cli("config", "set", "block_code_before_plan", "false")
        self.assertIsNone(self.decide(dict(edit)))
        self.run_cli("config", "set", "block_code_before_plan", "true")
        self.write_stage("w", "spec", GOOD["spec"])
        self.run_cli("approve", "w")
        add_nodes(self, "w")
        self.write_stage("w", "plan", GOOD["plan"])
        self.run_cli("approve", "w")
        self.assertIsNone(self.decide(dict(edit)))

    def test_shell_writes_to_protected_files(self):
        self.assertIsNotNone(self.decide({"tool_name": "Bash", "tool_input": {"command": f"echo x > {WF}/intent.md"}}))
        self.assertIsNotNone(self.decide({"tool_name": "Bash", "tool_input": {"command": f"rm {WF}/state.json"}}))
        self.assertIsNotNone(self.decide({"tool_name": "Bash", "tool_input": {"command": "chmod +w .intent-first/active"}}))
        self.assertIsNone(self.decide({"tool_name": "Bash", "tool_input": {"command": f"cat {WF}/intent.md 2>/dev/null"}}))
        self.assertIsNone(self.decide({"tool_name": "Bash", "tool_input": {"command": f"echo draft >> {WF}/spec.md"}}))

    def test_human_only_command_forms(self):
        for cmd in ("~/.local/bin/intent-first reopen w spec", "python3 -m intent_first deactivate",
                    "cd x && intent-first config set block_code_before_plan false", "python3 dist/intent-first.pyz uninstall -y"):
            self.assertIsNotNone(self.decide({"tool_name": "Bash", "tool_input": {"command": cmd}}), cmd)
        for cmd in ('grep -n "intent-first reopen" README.md', "intent-first config get name", "intent-first status w"):
            self.assertIsNone(self.decide({"tool_name": "Bash", "tool_input": {"command": cmd}}), cmd)

    def bash(self, cmd: str) -> str | None:
        return self.decide({"tool_name": "Bash", "tool_input": {"command": cmd}})

    def test_shell_cannot_switch_or_delete_workflows(self):
        self.assertIn("reserved", self.bash("intent-first activate other"))
        for cmd in ("rm -rf .intent-first/workflows/w", "mv .intent-first/workflows/w /tmp/", "rm -rf .intent-first",
                    f"rm {WF}/*", "Remove-Item -Recurse .intent-first/workflows"):
            self.assertIn("Workflow folders", self.bash(cmd) or "", cmd)

    def test_shell_writes_to_project_files_before_plan(self):
        for cmd in ("cat > src/app.py <<EOF\nprint(1)\nEOF", "echo x >> README.md", "sed -i 's/a/b/' src/app.py",
                    "rm src/*.py", "dd if=/dev/zero of=data.bin", "FOO=1 sudo tee src/x.py < in", "cp /tmp/a src/a.py"):
            self.assertIn("plan is approved", self.bash(cmd) or "", cmd)
        for cmd in ("echo x > /tmp/scratch", "ls 2>/dev/null", "pytest -q 2>&1 | tee /tmp/log", "cp src/a.py /tmp/",
                    "cat <<EOF > /tmp/x\n> .intent-first/workflows/w/intent.md\nEOF", "git diff > /tmp/d.patch"):
            self.assertIsNone(self.bash(cmd), cmd)

    def test_shell_reads_of_approved_files_are_allowed(self):
        self.run_cli("deactivate")
        for cmd in (f'grep -n "->" {WF}/intent.md', f"jq '.x > 1' {WF}/state.json", f"cat {WF}/intent.md | wc -l"):
            self.assertIsNone(self.bash(cmd), cmd)
        self.assertIn("approved and locked", self.bash(f"sed -i.bak 's/a/b/' {WF}/intent.md") or "")
        self.assertIn("approved and locked", self.bash(f"python3 -c \"open('{WF}/intent.md','w')\"") or "")
        self.assertIn("approved and locked", self.bash(f"echo 'unterminated > {WF}/intent.md") or "")

    def test_strict_approval(self):
        cmd = {"tool_name": "Bash", "tool_input": {"command": "intent-first approve w spec"}}
        self.assertIsNone(self.decide(dict(cmd)))
        self.run_cli("config", "set", "strict_approval", "true")
        self.assertIn("strict_approval", self.decide(dict(cmd)))

    def test_paths_outside_project_and_garbage(self):
        self.assertIsNone(self.decide({"tool_name": "Write", "tool_input": {"file_path": "/tmp/elsewhere.txt"}}))
        self.assertIsNone(self.decide({"tool_name": "Write", "tool_input": "not json"}))
        self.assertIsNone(self.decide({}))

    def test_no_workflows_means_no_opinion(self):
        shutil.rmtree(self.root / ".intent-first/workflows", onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))
        self.assertIsNone(self.decide({"tool_name": "Write", "tool_input": {"file_path": "src/app.py"}}))

    # -- the installed hook command, end to end --
    def run_hook(self, payload: str, cwd: Path, env_extra: dict | None = None) -> subprocess.CompletedProcess:
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.root), **(env_extra or {})}
        env.pop("INTENT_FIRST_ROOT", None)
        return subprocess.run(["sh", "-c", adapters.GUARD_SH], input=payload, cwd=cwd, env=env,
                              capture_output=True, text=True, timeout=30)

    @unittest.skipIf(os.name == "nt", "POSIX shell hook")
    def test_installed_hook_blocks_with_exit_2(self):
        r = self.run_hook(json.dumps({"tool_name": "Write", "tool_input": {"file_path": f"{WF}/intent.md"}, "cwd": str(self.root)}), self.root)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("approved and locked", r.stderr)
        self.assertEqual(json.loads(r.stdout)["permissionDecision"], "deny")
        audit = (self.root / ".intent-first/audit.log").read_text().splitlines()
        self.assertEqual(json.loads(audit[-1])["event"], "blocked")
        r = self.run_hook(json.dumps({"tool_name": "Read", "tool_input": {"file_path": "x"}}), self.root)
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        r = self.run_hook("{broken", self.root)
        self.assertEqual(r.returncode, 0)

    @unittest.skipIf(os.name == "nt", "POSIX shell hook")
    def test_hook_fails_open_without_guard_file(self):
        r = self.run_hook("{}", self.tmp, {"CLAUDE_PROJECT_DIR": str(self.tmp)})
        self.assertEqual(r.returncode, 0, r.stderr)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_opencode_plugin_bridge(self):
        script = self.tmp / "probe.mjs"
        script.write_text(
            "const { IntentFirstGuard } = await import(process.argv[2]);\n"
            "const h = await IntentFirstGuard({ worktree: process.argv[3], directory: process.argv[3] });\n"
            "const res = [];\n"
            "for (const f of ['intent.md', 'spec.md']) {\n"
            "  try { await h['tool.execute.before']({ tool: 'write' }, { args: { filePath: `.intent-first/workflows/w/${f}` } }); res.push('ok'); }\n"
            "  catch (e) { res.push('blocked'); }\n"
            "}\nconsole.log(res.join(','));\n"
        )
        plugin = (self.root / ".opencode/plugins/intent-first.js").as_uri()
        r = subprocess.run(["node", str(script), plugin, str(self.root)], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.stdout.strip(), "blocked,ok", r.stderr)

    def test_installed_guard_matches_package(self):
        self.assertEqual((self.root / ".intent-first/guard.py").read_text(), (SRC / "intent_first/guard.py").read_text())


if __name__ == "__main__":
    unittest.main()
