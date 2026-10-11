"""v2 → v3 migration of workflow data and old prompt/rule files."""

from __future__ import annotations

import json
import os
import stat
import unittest

from helpers import ProjectTestCase

V2_STATUS = """# Intent-First Workflow Status
workflow_id: "1"
parent_workflow: ""
spawned_workflows: [child-a]

stages:
  intent:
    status: locked       # draft | locked
    locked_at: "2026-01-01T00:00:00Z"
  spec:
    status: approved     # pending | draft | approved | locked
    current_phase: ""
    phases:
      codebase-explore:
        status: complete
    approved_by: "Ann"
    approved_at: "2026-01-02T00:00:00Z"
    locked_at: ""
  plan:
    status: draft
    approved_by: ""
  execution:
    status: complete
  artifacts:
    status: pending
"""


class MigrateTest(ProjectTestCase):
    def test_migrates_workflow_and_cleans_v2_files(self):
        d = self.root / ".intent-first/workflows/1"
        d.mkdir(parents=True)
        (d / "status.yml").write_text(V2_STATUS)
        for i, s in enumerate(("intent", "spec", "plan", "execution", "artifacts"), 1):
            (d / f"s{i}_{s}.md").write_text(f"# {s}\n")
        os.chmod(d / "s1_intent.md", 0o444)
        (d / "execution-graph.json").write_text(json.dumps({"graph": {"nodes": [{"id": "a", "name": "A", "depends_on": [], "status": "complete"}]}}))
        (self.root / ".github/prompts").mkdir(parents=True)
        (self.root / ".github/prompts/wf-spec.prompt.md").write_text("old")
        (self.root / ".github/prompts/other.prompt.md").write_text("keep")
        (self.root / ".github/copilot-instructions.md").write_text("For the Intent-First Agentic Workflow, see `.intent-first/rules.md`.\n")
        (self.root / "CLAUDE.md").write_text("# Mine\n\nFor the Intent-First Agentic Workflow, see `.intent-first/rules.md`.\n")
        (self.root / ".intent-first/rules.md").write_text("rules")

        out = self.run_cli("migrate")
        self.assertIn("1 (2/4 stages approved)", out)
        st = self.state("1")
        self.assertEqual(st["stages"]["spec"]["approved_by"], "Ann")
        self.assertIsNone(st["stages"]["execution"]["approved_at"])  # not contiguous with an approved plan
        self.assertEqual(st["children"], ["child-a"])
        self.assertEqual(st["graph"]["nodes"][0]["status"], "complete")
        self.assertTrue((d / "intent.md").is_file())
        self.assertEqual((d / "v2-artifacts.md").read_text(encoding="utf-8"), "# artifacts\n")
        self.assertFalse(os.stat(d / "intent.md").st_mode & stat.S_IWUSR)
        self.assertTrue(os.stat(d / "plan.md").st_mode & stat.S_IWUSR)
        self.assertFalse((d / "status.yml").exists())
        self.assertFalse((self.root / ".github/prompts/wf-spec.prompt.md").exists())
        self.assertTrue((self.root / ".github/prompts/other.prompt.md").exists())
        self.assertFalse((self.root / ".github/copilot-instructions.md").exists())
        self.assertEqual((self.root / "CLAUDE.md").read_text(encoding="utf-8"), "# Mine\n")
        self.run_cli("check", "1", "spec", expect=1)  # v2 content lacks v3 sections, but integrity is fine
        self.assertNotIn("changed after approval", self.run_cli("check", "1", "spec", expect=1))
        self.assertIn("Nothing to migrate", self.run_cli("migrate"))


if __name__ == "__main__":
    unittest.main()
