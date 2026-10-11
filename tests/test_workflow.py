"""CLI workflow lifecycle: new → approve each stage → report, plus checks, graph, reopen, config."""

from __future__ import annotations

import json
import os
import stat
import unittest

from helpers import GOOD, ProjectTestCase, add_nodes, approve_through, complete_nodes


class LifecycleTest(ProjectTestCase):
    def test_new_auto_numbers_and_activates(self):
        self.run_cli("new")
        self.run_cli("new")
        self.assertTrue(self.wf_path("2", "intent.md").is_file())
        self.assertFalse(self.wf_path("2", "artifacts.md").exists())
        self.assertEqual((self.root / ".intent-first/active").read_text().strip(), "2")
        self.run_cli("new", "named", "--no-activate")
        self.assertEqual((self.root / ".intent-first/active").read_text().strip(), "2")

    def test_new_rejects_bad_and_duplicate_ids(self):
        self.run_cli("new", "../escape", expect=1)
        self.run_cli("new", "a")
        self.run_cli("new", "a", expect=1)

    def test_full_lifecycle_writes_report(self):
        self.run_cli("new", "auth")
        approve_through(self, "auth", "execution")
        st = self.state("auth")
        for s in ("intent", "spec", "plan", "execution"):
            self.assertEqual(st["stages"][s]["approved_by"], "Tester")
            self.assertFalse(os.stat(self.wf_path("auth", f"{s}.md")).st_mode & stat.S_IWUSR)
        self.assertFalse((self.root / ".intent-first/active").exists())
        report = self.wf_path("auth", "report.md").read_text()
        self.assertIn("# GitHub login", report)
        self.assertIn("| **G1** Users can log in with GitHub. | AC1 ✅ | met |", report)
        self.assertIn("| **G2** Password login keeps working. | AC2 ✅ | met |", report)
        self.assertIn("`ui` ui (covers AC1, AC2)", report)
        self.assertIn("- Add GitLab login", report)
        self.assertIn("Done. Report:", self.run_cli("status", "auth"))
        self.assertEqual(self.run_cli("report", "auth").strip(), report.strip())

    def test_report_includes_diff_since_plan_approval(self):
        (self.root / "app.py").write_text("a = 1\n")
        os.system(f"cd '{self.root}' && git add app.py && git -c user.name=t -c user.email=t@t commit -qm init")
        self.run_cli("new", "w")
        approve_through(self, "w", "plan")
        self.assertTrue(self.state("w")["git_base"])
        (self.root / "app.py").write_text("a = 2\nb = 3\n")
        report = self.run_cli("report", "w")
        self.assertIn("## Changes", report)
        self.assertIn("app.py", report)
        self.assertIn("AC1 ⬜", report)
        self.assertIn("not met", report)

    def test_stage_order_is_enforced(self):
        self.run_cli("new", "w")
        out = self.run_cli("approve", "w", "spec", expect=1)
        self.assertIn("Approve intent before spec", out)

    def test_open_questions_and_force(self):
        self.run_cli("new", "w")
        self.assertIn("'## Goals' is empty", self.run_cli("approve", "w", expect=1))
        approve_through(self, "w", "intent")
        self.write_stage("w", "spec", GOOD["spec"].replace("## Open Questions\nNone", "## Open Questions\n- Which provider?"))
        self.assertIn("open question: - Which provider?", self.run_cli("check", "w", expect=1))
        self.assertIn("--force", self.run_cli("approve", "w", "spec", "--force"))
        self.assertTrue(self.state("w")["stages"]["spec"]["forced"])

    def test_resolved_questions_and_defer_markers(self):
        self.run_cli("new", "w")
        approve_through(self, "w", "intent")
        spec = GOOD["spec"].replace("## Open Questions\nNone", "## Open Questions\n- [x] Which provider? GitHub.")
        self.write_stage("w", "spec", spec.replace("next to passwords.", "next to passwords.\nTODO: rate limits"))
        out = self.run_cli("check", "w", expect=1)
        self.assertIn("unresolved marker", out)
        self.assertNotIn("open question", out)
        self.write_stage("w", "spec", spec.replace(
            "next to passwords.",
            "next to passwords.\nTODO rate limits [APPROVED-DEFER: Ann 2026-10-01]\n```\n# TODO in code is fine\n## not a heading\n```",
        ))
        self.run_cli("check", "w")

    def test_integrity_detects_changes_after_approval(self):
        self.run_cli("new", "w")
        approve_through(self, "w", "intent")
        self.write_stage("w", "intent", GOOD["intent"] + "sneaky\n")
        self.assertIn("changed after approval", self.run_cli("check", "w", "spec", expect=1))
        self.assertTrue(json.loads(self.run_cli("status", "w", "--json"))["integrity_issues"])

    def test_reopen_cascades_and_unlocks(self):
        self.run_cli("new", "w")
        approve_through(self, "w", "spec")
        self.assertIn("intent, spec", self.run_cli("reopen", "w", "intent"))
        self.assertTrue(os.stat(self.wf_path("w", "intent.md")).st_mode & stat.S_IWUSR)
        self.assertEqual(json.loads(self.run_cli("status", "w", "--json"))["current_stage"], "intent")
        self.run_cli("reopen", "w", "plan", expect=1)

    def test_parent_child_links(self):
        self.run_cli("new", "parent")
        self.run_cli("new", "child", "--parent", "parent")
        self.assertEqual(self.state("parent")["children"], ["child"])
        self.assertEqual(self.state("child")["parent"], "parent")
        self.run_cli("new", "orphan", "--parent", "missing", expect=1)

    def test_list_and_status_json(self):
        self.assertIn("No workflows", self.run_cli("list"))
        self.run_cli("new", "a")
        rows = json.loads(self.run_cli("list", "--json"))
        self.assertEqual((rows[0]["id"], rows[0]["current_stage"], rows[0]["active"]), ("a", "intent", True))

    def test_old_schema_is_rejected_with_hint(self):
        self.run_cli("new", "a")
        self.wf_path("a", "state.json").write_text('{"schema_version": 2}')
        self.assertIn("migrate", self.run_cli("status", "a", expect=1))


class TraceabilityTest(ProjectTestCase):
    """Intent mapping is enforced at every gate through G → AC → node → result IDs."""

    def setUp(self):
        super().setUp()
        self.run_cli("new", "w")

    def test_goals_must_be_numbered(self):
        self.write_stage("w", "intent", "# I\n\n## Goals\n- Users can log in.\n")
        self.assertIn("number each goal", self.run_cli("check", "w", expect=1))
        self.write_stage("w", "intent", "# I\n\n## Goals\nUsers can log in.\n")
        self.assertIn("number each goal", self.run_cli("check", "w", expect=1))
        self.write_stage("w", "intent", "# I\n\n## Goals\n- G1: a\n- G1: b\n")
        self.assertIn("duplicate goal G1", self.run_cli("check", "w", expect=1))

    def test_spec_must_cover_every_goal_with_wellformed_criteria(self):
        approve_through(self, "w", "intent")
        self.write_stage("w", "spec", GOOD["spec"].replace("- AC2 (G2): Password login is unchanged.", "- AC2 (G9): x\n- AC3: no goal"))
        out = self.run_cli("check", "w", expect=1)
        self.assertIn("goal G2 has no acceptance criterion", out)
        self.assertIn("AC2 refers to unknown goal(s) G9", out)
        self.assertIn("write criteria as `- AC1 (G1): ...`", out)

    def test_spec_notes_file_level_detail(self):
        approve_through(self, "w", "intent")
        self.write_stage("w", "spec", GOOD["spec"].replace("Use the provider SDK.", "Edit src/auth/login.py first."))
        out = self.run_cli("check", "w")
        self.assertIn("note: spec.md mentions source files (src/auth/login.py)", out)
        self.write_stage("w", "spec", GOOD["spec"].replace("## Interfaces\nNone", "## Interfaces\nPlugins export `hooks.py`."))
        self.assertNotIn("note:", self.run_cli("check", "w"))

    def test_plan_coverage_steps_and_verification(self):
        approve_through(self, "w", "spec")
        self.write_stage("w", "plan", GOOD["plan"])
        self.assertIn("execution graph is empty", self.run_cli("check", "w", expect=1))
        self.run_cli("graph", "add", "w", "api", "--covers", "AC1")
        self.run_cli("graph", "add", "w", "db", "--covers", "AC9", expect=1)
        self.run_cli("graph", "add", "w", "db", expect=2)  # --covers is required
        out = self.run_cli("check", "w", expect=1)
        self.assertIn("AC2 is not covered by any graph node", out)
        self.assertIn("step '### ui' has no graph node", out)
        self.run_cli("graph", "add", "w", "ui", "--covers", "ac2", "--deps", "api")
        self.write_stage("w", "plan", GOOD["plan"].replace("- AC2: `pytest -k password`", ""))
        self.assertIn("does not say how AC2 is proven", self.run_cli("check", "w", expect=1))
        self.write_stage("w", "plan", GOOD["plan"])
        self.run_cli("approve", "w")

    def test_graph_needs_approved_spec(self):
        approve_through(self, "w", "intent")
        self.assertIn("approve the spec first", self.run_cli("graph", "add", "w", "a", "--covers", "AC1", expect=1))

    def test_execution_needs_a_passing_result_per_criterion(self):
        approve_through(self, "w", "plan")
        complete_nodes(self, "w")
        self.write_stage("w", "execution", GOOD["execution"].replace("- AC2: pass — `pytest -k password` (5 passed)", ""))
        self.assertIn("no result for AC2", self.run_cli("check", "w", expect=1))
        failing = GOOD["execution"].replace("AC2: pass", "AC2: fail")
        self.write_stage("w", "execution", failing)
        self.assertIn("AC2 failed", self.run_cli("check", "w", expect=1))
        self.write_stage("w", "execution", failing.replace("(5 passed)", "(5 passed) [APPROVED-DEFER: Ann 2026-10-12]"))
        self.run_cli("approve", "w")
        self.assertIn("AC2 ❌", self.wf_path("w", "report.md").read_text())


class GraphTest(ProjectTestCase):
    def setUp(self):
        super().setUp()
        self.run_cli("new", "w")
        approve_through(self, "w", "spec")

    def test_graph_flow(self):
        self.run_cli("graph", "add", "w", "db", "--covers", "AC1", "--name", "schema")
        self.run_cli("graph", "add", "w", "api", "--covers", "AC1", "--deps", "db")
        self.run_cli("graph", "add", "w", "ui", "--covers", "AC2", "--deps", "api")
        self.run_cli("graph", "add", "w", "bad", "--covers", "AC1", "--deps", "nope", expect=1)
        self.run_cli("graph", "set", "w", "db", "in_progress", expect=1)  # plan not approved yet
        self.write_stage("w", "plan", GOOD["plan"].replace("## Steps\n", "## Steps\n### db\nSchema.\n\n"))
        self.run_cli("approve", "w")
        self.run_cli("graph", "add", "w", "late", "--covers", "AC1", expect=1)  # frozen after plan approval
        self.assertEqual([n["id"] for n in json.loads(self.run_cli("graph", "ready", "w", "--json"))], ["db"])
        self.run_cli("graph", "set", "w", "api", "in_progress", expect=1)  # deps unmet
        self.run_cli("graph", "set", "w", "db", "in_progress")
        self.run_cli("graph", "set", "w", "db", "failed")
        nodes = {n["id"]: n["status"] for n in json.loads(self.run_cli("graph", "show", "w", "--json"))}
        self.assertEqual(nodes, {"db": "failed", "api": "blocked", "ui": "blocked"})
        self.run_cli("graph", "set", "w", "db", "complete")
        nodes = {n["id"]: n["status"] for n in json.loads(self.run_cli("graph", "show", "w", "--json"))}
        self.assertEqual(nodes, {"db": "complete", "api": "pending", "ui": "pending"})
        self.write_stage("w", "execution", GOOD["execution"])
        self.assertIn("not complete: api, ui", self.run_cli("check", "w", "execution", expect=1))
        complete_nodes(self, "w")
        self.run_cli("approve", "w", "execution")
        self.assertIn("covers: AC2", self.run_cli("graph", "show", "w"))

    def test_cycle_rejected_and_rm(self):
        add_nodes(self, "w")
        self.run_cli("graph", "rm", "w", "api", expect=1)  # ui depends on it
        self.run_cli("graph", "rm", "w", "ui")
        self.run_cli("graph", "rm", "w", "api")
        self.assertIn("empty graph", self.run_cli("graph", "show", "w"))

    def test_execution_unchecked_items(self):
        add_nodes(self, "w")
        self.write_stage("w", "plan", GOOD["plan"])
        self.run_cli("approve", "w")
        complete_nodes(self, "w")
        self.write_stage("w", "execution", GOOD["execution"] + "\n- [ ] forgot\n")
        self.assertIn("unchecked", self.run_cli("check", "w", expect=1))


class ConfigTest(ProjectTestCase):
    def test_name_and_project_flags(self):
        os.environ.pop("INTENT_FIRST_USER")
        self.run_cli("config", "set", "name", "Ann Lee")
        self.assertEqual(self.run_cli("config", "get", "name").strip(), "Ann Lee")
        self.run_cli("config", "set", "strict_approval", "true")
        self.assertEqual(self.run_cli("config", "get", "strict_approval").strip(), "true")
        self.run_cli("config", "set", "strict_approval", "maybe", expect=1)
        self.run_cli("config", "set", "bogus", "1", expect=1)
        self.run_cli("new", "w")
        self.write_stage("w", "intent", GOOD["intent"])
        self.run_cli("approve", "w", "--yolo")
        self.assertEqual(self.state("w")["stages"]["intent"]["approved_by"], "Ann Lee (yolo)")


if __name__ == "__main__":
    unittest.main()
