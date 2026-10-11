"""CLI workflow lifecycle: new → approve each stage → done, plus checks, graph, reopen, config."""

from __future__ import annotations

import json
import os
import stat
import unittest

from helpers import GOOD, ProjectTestCase


class LifecycleTest(ProjectTestCase):
    def test_new_auto_numbers_and_activates(self):
        self.run_cli("new")
        self.run_cli("new")
        self.assertTrue(self.wf_path("2", "intent.md").is_file())
        self.assertEqual((self.root / ".intent-first/active").read_text().strip(), "2")
        self.run_cli("new", "named", "--no-activate")
        self.assertEqual((self.root / ".intent-first/active").read_text().strip(), "2")

    def test_new_rejects_bad_and_duplicate_ids(self):
        self.run_cli("new", "../escape", expect=1)
        self.run_cli("new", "a")
        self.run_cli("new", "a", expect=1)

    def test_full_lifecycle(self):
        self.run_cli("new", "auth")
        for stage in ("intent", "spec", "plan"):
            self.write_stage("auth", stage, GOOD[stage])
            self.run_cli("approve", "auth")
        self.write_stage("auth", "execution", GOOD["execution"])
        self.write_stage("auth", "artifacts", GOOD["artifacts"])
        self.run_cli("approve", "auth", "execution")
        out = self.run_cli("approve", "auth", "artifacts")
        self.assertIn("Workflow complete", out)
        st = self.state("auth")
        for s in ("intent", "spec", "plan", "execution", "artifacts"):
            self.assertEqual(st["stages"][s]["approved_by"], "Tester")
            self.assertFalse(os.stat(self.wf_path("auth", f"{s}.md")).st_mode & stat.S_IWUSR)
        self.assertFalse((self.root / ".intent-first/active").exists())
        self.run_cli("check", "auth", "artifacts")
        self.assertIn("Done.", self.run_cli("status", "auth"))

    def test_stage_order_is_enforced(self):
        self.run_cli("new", "w")
        out = self.run_cli("approve", "w", "spec", expect=1)
        self.assertIn("Approve intent before spec", out)

    def test_check_blocks_empty_and_open_questions(self):
        self.run_cli("new", "w")
        out = self.run_cli("approve", "w", expect=1)
        self.assertIn("'## Goal' is empty", out)
        self.write_stage("w", "intent", GOOD["intent"])
        self.run_cli("approve", "w")
        self.write_stage("w", "spec", GOOD["spec"].replace("## Open Questions\nNone", "## Open Questions\n- Which provider?"))
        out = self.run_cli("check", "w", expect=1)
        self.assertIn("open question: - Which provider?", out)
        out = self.run_cli("approve", "w", "spec", "--force")
        self.assertIn("--force", out)
        self.assertTrue(self.state("w")["stages"]["spec"]["forced"])

    def test_resolved_questions_and_defer_markers(self):
        self.run_cli("new", "w")
        self.write_stage("w", "intent", GOOD["intent"])
        self.run_cli("approve", "w")
        spec = GOOD["spec"].replace("## Open Questions\nNone", "## Open Questions\n- [x] Which provider? GitHub.")
        self.write_stage("w", "spec", spec.replace("Login via OAuth.", "Login via OAuth.\nTODO: rate limits"))
        out = self.run_cli("check", "w", expect=1)
        self.assertIn("unresolved marker", out)
        self.assertNotIn("open question", out)
        self.write_stage("w", "spec", spec.replace(
            "Login via OAuth.",
            "Login via OAuth.\nTODO rate limits [APPROVED-DEFER: Ann 2026-10-01]\n```\n# TODO in code is fine\n```",
        ))
        self.run_cli("check", "w")

    def test_integrity_detects_changes_after_approval(self):
        self.run_cli("new", "w")
        self.write_stage("w", "intent", GOOD["intent"])
        self.run_cli("approve", "w")
        self.write_stage("w", "intent", GOOD["intent"] + "sneaky\n")
        out = self.run_cli("check", "w", "spec", expect=1)
        self.assertIn("changed after approval", out)
        status = json.loads(self.run_cli("status", "w", "--json"))
        self.assertTrue(status["integrity_issues"])

    def test_reopen_cascades_and_unlocks(self):
        self.run_cli("new", "w")
        for stage in ("intent", "spec"):
            self.write_stage("w", stage, GOOD[stage])
            self.run_cli("approve", "w")
        out = self.run_cli("reopen", "w", "intent")
        self.assertIn("intent, spec", out)
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
        self.assertEqual(rows[0]["id"], "a")
        self.assertEqual(rows[0]["current_stage"], "intent")
        self.assertTrue(rows[0]["active"])

    def test_old_schema_is_rejected_with_hint(self):
        self.run_cli("new", "a")
        self.wf_path("a", "state.json").write_text('{"schema_version": 2}')
        self.assertIn("migrate", self.run_cli("status", "a", expect=1))


class GraphTest(ProjectTestCase):
    def setUp(self):
        super().setUp()
        self.run_cli("new", "w")
        for stage in ("intent", "spec"):
            self.write_stage("w", stage, GOOD[stage])
            self.run_cli("approve", "w")

    def test_graph_flow(self):
        self.run_cli("graph", "add", "w", "db", "--name", "schema")
        self.run_cli("graph", "add", "w", "api", "--deps", "db")
        self.run_cli("graph", "add", "w", "ui", "--deps", "api")
        self.run_cli("graph", "add", "w", "bad", "--deps", "nope", expect=1)
        self.run_cli("graph", "set", "w", "db", "in_progress", expect=1)  # plan not approved yet
        self.write_stage("w", "plan", GOOD["plan"])
        self.run_cli("approve", "w")
        self.run_cli("graph", "add", "w", "late", expect=1)  # graph frozen after plan approval
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
        out = self.run_cli("check", "w", "execution", expect=1)
        self.assertIn("not complete: api, ui", out)
        for n in ("api", "ui"):
            self.run_cli("graph", "set", "w", n, "in_progress")
            self.run_cli("graph", "set", "w", n, "complete")
        self.run_cli("approve", "w", "execution")
        self.assertIn("ui", self.run_cli("graph", "show", "w"))

    def test_cycle_rejected_and_rm(self):
        self.run_cli("graph", "add", "w", "a")
        self.run_cli("graph", "add", "w", "b", "--deps", "a")
        self.run_cli("graph", "rm", "w", "a", expect=1)  # b depends on it
        self.run_cli("graph", "rm", "w", "b")
        self.run_cli("graph", "rm", "w", "a")
        self.assertIn("empty graph", self.run_cli("graph", "show", "w"))

    def test_execution_unchecked_items(self):
        self.write_stage("w", "plan", GOOD["plan"])
        self.run_cli("approve", "w")
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
