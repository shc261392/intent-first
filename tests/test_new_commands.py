#!/usr/bin/env python3
"""
Tests for new Intent-First CLI commands:
- configure
- phase-update, phase-list
- graph create/show/ready/update/validate
- spawn, link
- status
- DAG engine: cycle detection, topological sort, ready nodes, failure propagation
"""

import importlib.util
import importlib.machinery
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CLITestBase(unittest.TestCase):
    """Base class with workflow setup helpers."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="intent-first-test-")
        self.addCleanup(shutil.rmtree, self.test_dir, ignore_errors=True)
        self.workflow_id = "test-1"
        self.workflow_dir = Path(self.test_dir) / "workflows" / self.workflow_id
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        self.cli_path = Path(__file__).parent.parent / "cli" / "intent-first"
        self.config_dir = Path(self.test_dir) / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._create_status_yml()

    def tearDown(self):
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def _create_status_yml(self):
        """Create a status.yml with phase support."""
        status_yml = self.workflow_dir / "status.yml"
        status_yml.write_text(f"""\
# Intent-First Workflow Status
workflow_id: "{self.workflow_id}"
parent_workflow: ""
spawned_from_stage: ""
spawned_workflows: []
linked_workflows: []
tags: []
priority: ""

stages:
  intent:
    status: draft
    locked_at: ""

  spec:
    status: pending
    current_phase: ""
    phases:
      codebase-explore:
        status: pending
        started_at: ""
        completed_at: ""
      intent-mapping:
        status: pending
        started_at: ""
        completed_at: ""
      intent-lock:
        status: pending
        completed_at: ""
      research:
        status: pending
        started_at: ""
        completed_at: ""
      spec-drafting:
        status: pending
        started_at: ""
        completed_at: ""
      spec-iteration:
        status: pending
        started_at: ""
        completed_at: ""
      spec-lock:
        status: pending
        completed_at: ""
    approved_by: ""
    approved_at: ""
    locked_at: ""

  plan:
    status: pending
    current_phase: ""
    phases:
      execution-graph-draft:
        status: pending
        started_at: ""
        completed_at: ""
      plan-iteration:
        status: pending
        started_at: ""
        completed_at: ""
      execution-graph-finalization:
        status: pending
        started_at: ""
        completed_at: ""
      plan-lock:
        status: pending
        completed_at: ""
    derived_from: "s2_spec.md"
    approved_by: ""
    approved_at: ""
    locked_at: ""

  execution:
    status: pending
    current_phase: ""
    phases:
      execution-iteration:
        status: pending
        started_at: ""
        completed_at: ""
      execution-lock:
        status: pending
        completed_at: ""
    started_at: ""
    completed_at: ""
    locked_at: ""

  artifacts:
    status: pending
    current_phase: ""
    phases:
      artifacts-iteration:
        status: pending
        started_at: ""
        completed_at: ""
      new-workflow-spawning:
        status: pending
        started_at: ""
        completed_at: ""
      artifacts-lock:
        status: pending
        completed_at: ""
    completed_at: ""
    locked_at: ""
""")
        return status_yml

    def _create_stage_files(self):
        """Create minimal stage files."""
        for f in ["s1_intent.md", "s2_spec.md", "s3_plan.md", "s4_execution.md", "s5_artifacts.md"]:
            (self.workflow_dir / f).write_text(f"# {f}\n\nContent here.")

    def _run_cli(self, args, env_extra=None):
        """Run CLI command and return (exit_code, stdout, stderr)."""
        env = os.environ.copy()
        env["INTENT_FIRST_WORKFLOW_DIR"] = str(Path(self.test_dir) / "workflows")
        env["INTENT_FIRST_HOME"] = str(self.config_dir)
        env["INTENT_FIRST_TEMPLATE_DIR"] = str(
            Path(__file__).parent.parent / "templates"
        )
        if env_extra:
            env.update(env_extra)
        cmd = [str(self.cli_path)] + args
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return result.returncode, result.stdout, result.stderr


class TestConfigure(CLITestBase):
    """Tests for the configure command."""

    def test_configure_set_name(self):
        ec, out, err = self._run_cli(["configure", "--name", "Alice"])
        self.assertEqual(ec, 0, f"stderr: {err}")
        self.assertIn("Alice", out)

    def test_configure_get_name(self):
        self._run_cli(["configure", "--name", "Bob"])
        ec, out, err = self._run_cli(["configure", "--get", "name"])
        self.assertEqual(ec, 0, f"stderr: {err}")
        self.assertIn("Bob", out.strip())

    def test_configure_get_missing_key(self):
        ec, out, err = self._run_cli(["configure", "--get", "nonexistent"])
        self.assertNotEqual(ec, 0)

    def test_configure_set_max_parallelism(self):
        ec, out, err = self._run_cli(["configure", "--max-parallelism", "4"])
        self.assertEqual(ec, 0, f"stderr: {err}")
        ec2, out2, _ = self._run_cli(["configure", "--get", "max_parallelism"])
        self.assertEqual(ec2, 0)
        self.assertIn("4", out2.strip())

    def test_configure_show_all(self):
        self._run_cli(["configure", "--name", "Charlie"])
        ec, out, err = self._run_cli(["configure"])
        self.assertEqual(ec, 0, f"stderr: {err}")
        self.assertIn("name", out)
        self.assertIn("Charlie", out)


class TestPhaseUpdate(CLITestBase):
    """Tests for phase-update command."""

    def test_phase_update_basic(self):
        ec, out, err = self._run_cli([
            "phase-update", self.workflow_id, "spec", "codebase-explore",
            "--status", "in_progress"
        ])
        self.assertEqual(ec, 0, f"stderr: {err}")
        self.assertIn("codebase-explore", out)

    def test_phase_update_complete(self):
        self._run_cli([
            "phase-update", self.workflow_id, "spec", "codebase-explore",
            "--status", "in_progress", "--started-at", "auto"
        ])
        ec, out, err = self._run_cli([
            "phase-update", self.workflow_id, "spec", "codebase-explore",
            "--status", "complete", "--completed-at", "auto"
        ])
        self.assertEqual(ec, 0, f"stderr: {err}")
        self.assertIn("complete", out)

    def test_phase_update_invalid_phase(self):
        ec, out, err = self._run_cli([
            "phase-update", self.workflow_id, "spec", "nonexistent-phase",
            "--status", "in_progress"
        ])
        self.assertNotEqual(ec, 0)

    def test_phase_update_invalid_status(self):
        ec, out, err = self._run_cli([
            "phase-update", self.workflow_id, "spec", "codebase-explore",
            "--status", "invalid_status"
        ])
        self.assertNotEqual(ec, 0)

    def test_phase_update_plan_phases(self):
        ec, out, err = self._run_cli([
            "phase-update", self.workflow_id, "plan", "execution-graph-draft",
            "--status", "in_progress"
        ])
        self.assertEqual(ec, 0, f"stderr: {err}")

    def test_phase_update_execution_phases(self):
        ec, out, err = self._run_cli([
            "phase-update", self.workflow_id, "execution", "execution-iteration",
            "--status", "in_progress"
        ])
        self.assertEqual(ec, 0, f"stderr: {err}")

    def test_phase_update_artifacts_phases(self):
        ec, out, err = self._run_cli([
            "phase-update", self.workflow_id, "artifacts", "artifacts-iteration",
            "--status", "in_progress"
        ])
        self.assertEqual(ec, 0, f"stderr: {err}")


class TestPhaseList(CLITestBase):
    """Tests for phase-list command."""

    def test_phase_list_spec(self):
        ec, out, err = self._run_cli(["phase-list", self.workflow_id, "spec"])
        self.assertEqual(ec, 0, f"stderr: {err}")
        self.assertIn("codebase-explore", out)
        self.assertIn("spec-lock", out)

    def test_phase_list_plan(self):
        ec, out, err = self._run_cli(["phase-list", self.workflow_id, "plan"])
        self.assertEqual(ec, 0, f"stderr: {err}")
        self.assertIn("execution-graph-draft", out)
        self.assertIn("plan-lock", out)

    def test_phase_list_invalid_stage(self):
        ec, out, err = self._run_cli(["phase-list", self.workflow_id, "invalid"])
        self.assertNotEqual(ec, 0)


class TestGraph(CLITestBase):
    """Tests for graph commands."""

    def _graph_path(self):
        return self.workflow_dir / "execution-graph.json"

    def _create_graph_with_nodes(self):
        """Create a graph with some test nodes."""
        self._run_cli(["graph", "create", self.workflow_id])
        gpath = self._graph_path()
        data = {
            "graph": {
                "nodes": [
                    {
                        "id": "schema",
                        "name": "Create schema",
                        "depends_on": [],
                        "plan_items": ["Create users table"],
                        "status": "pending",
                        "started_at": "",
                        "completed_at": "",
                        "assigned_to": ""
                    },
                    {
                        "id": "dal",
                        "name": "Data access layer",
                        "depends_on": ["schema"],
                        "plan_items": ["UserRepository"],
                        "status": "pending",
                        "started_at": "",
                        "completed_at": "",
                        "assigned_to": ""
                    },
                    {
                        "id": "api",
                        "name": "API endpoints",
                        "depends_on": ["dal"],
                        "plan_items": ["POST /auth/login"],
                        "status": "pending",
                        "started_at": "",
                        "completed_at": "",
                        "assigned_to": ""
                    },
                    {
                        "id": "auth-middleware",
                        "name": "Auth middleware",
                        "depends_on": ["schema"],
                        "plan_items": ["JWT middleware"],
                        "status": "pending",
                        "started_at": "",
                        "completed_at": "",
                        "assigned_to": ""
                    }
                ],
                "parallelism": {
                    "max_graph": 3,
                    "max_agent": 1,
                    "max_configured": None,
                    "effective": 1
                }
            }
        }
        gpath.write_text(json.dumps(data, indent=2))

    def test_graph_create(self):
        ec, out, err = self._run_cli(["graph", "create", self.workflow_id])
        self.assertEqual(ec, 0, f"stderr: {err}")
        self.assertTrue(self._graph_path().exists())

    def test_graph_create_already_exists(self):
        self._run_cli(["graph", "create", self.workflow_id])
        ec, out, err = self._run_cli(["graph", "create", self.workflow_id])
        self.assertNotEqual(ec, 0)

    def test_graph_show_empty(self):
        self._run_cli(["graph", "create", self.workflow_id])
        ec, out, err = self._run_cli(["graph", "show", self.workflow_id])
        self.assertEqual(ec, 0, f"stderr: {err}")
        self.assertIn("empty", out.lower())

    def test_graph_show_with_nodes(self):
        self._create_graph_with_nodes()
        ec, out, err = self._run_cli(["graph", "show", self.workflow_id])
        self.assertEqual(ec, 0, f"stderr: {err}")
        self.assertIn("schema", out)
        self.assertIn("dal", out)
        self.assertIn("api", out)

    def test_graph_ready_initial(self):
        self._create_graph_with_nodes()
        ec, out, err = self._run_cli(["graph", "ready", self.workflow_id])
        self.assertEqual(ec, 0, f"stderr: {err}")
        # Only schema should be ready (no deps)
        self.assertIn("schema", out)
        self.assertNotIn("dal", out)
        self.assertNotIn("api", out)

    def test_graph_update_start_node(self):
        self._create_graph_with_nodes()
        ec, out, err = self._run_cli([
            "graph", "update", self.workflow_id, "schema", "--status", "in_progress"
        ])
        self.assertEqual(ec, 0, f"stderr: {err}")
        # Verify status in file
        data = json.loads(self._graph_path().read_text())
        node = [n for n in data["graph"]["nodes"] if n["id"] == "schema"][0]
        self.assertEqual(node["status"], "in_progress")
        self.assertNotEqual(node["started_at"], "")

    def test_graph_update_complete_node(self):
        self._create_graph_with_nodes()
        self._run_cli(["graph", "update", self.workflow_id, "schema", "--status", "in_progress"])
        ec, out, err = self._run_cli([
            "graph", "update", self.workflow_id, "schema", "--status", "complete"
        ])
        self.assertEqual(ec, 0, f"stderr: {err}")
        # Now dal and auth-middleware should be ready
        ec2, out2, _ = self._run_cli(["graph", "ready", self.workflow_id])
        self.assertIn("dal", out2)
        self.assertIn("auth-middleware", out2)

    def test_graph_update_fail_node_propagates(self):
        self._create_graph_with_nodes()
        # Complete schema first
        self._run_cli(["graph", "update", self.workflow_id, "schema", "--status", "in_progress"])
        self._run_cli(["graph", "update", self.workflow_id, "schema", "--status", "complete"])
        # Fail dal
        self._run_cli(["graph", "update", self.workflow_id, "dal", "--status", "in_progress"])
        ec, out, err = self._run_cli([
            "graph", "update", self.workflow_id, "dal", "--status", "failed"
        ])
        self.assertEqual(ec, 0, f"stderr: {err}")
        # api should be blocked (depends on dal)
        data = json.loads(self._graph_path().read_text())
        api_node = [n for n in data["graph"]["nodes"] if n["id"] == "api"][0]
        self.assertEqual(api_node["status"], "blocked")
        # auth-middleware should still be pending/ready (depends on schema, not dal)
        auth_node = [n for n in data["graph"]["nodes"] if n["id"] == "auth-middleware"][0]
        self.assertIn(auth_node["status"], ("pending",))

    def test_graph_update_reset_node(self):
        self._create_graph_with_nodes()
        self._run_cli(["graph", "update", self.workflow_id, "schema", "--status", "in_progress"])
        self._run_cli(["graph", "update", self.workflow_id, "schema", "--status", "failed"])
        ec, out, err = self._run_cli([
            "graph", "update", self.workflow_id, "schema", "--status", "pending"
        ])
        self.assertEqual(ec, 0, f"stderr: {err}")
        data = json.loads(self._graph_path().read_text())
        node = [n for n in data["graph"]["nodes"] if n["id"] == "schema"][0]
        self.assertEqual(node["status"], "pending")

    def test_graph_update_unknown_node(self):
        self._create_graph_with_nodes()
        ec, out, err = self._run_cli([
            "graph", "update", self.workflow_id, "nonexistent", "--status", "complete"
        ])
        self.assertNotEqual(ec, 0)

    def test_graph_validate_valid(self):
        self._create_graph_with_nodes()
        ec, out, err = self._run_cli(["graph", "validate", self.workflow_id])
        self.assertEqual(ec, 0, f"stderr: {err}")
        self.assertIn("valid", out.lower())

    def test_graph_validate_cycle(self):
        self._run_cli(["graph", "create", self.workflow_id])
        gpath = self._graph_path()
        data = {
            "graph": {
                "nodes": [
                    {"id": "a", "name": "A", "depends_on": ["b"], "status": "pending"},
                    {"id": "b", "name": "B", "depends_on": ["a"], "status": "pending"},
                ],
                "parallelism": {"max_graph": 3, "max_agent": 1, "max_configured": None, "effective": 1}
            }
        }
        gpath.write_text(json.dumps(data, indent=2))
        ec, out, err = self._run_cli(["graph", "validate", self.workflow_id])
        self.assertNotEqual(ec, 0)
        self.assertIn("cycle", out.lower())

    def test_graph_validate_missing_dep(self):
        self._run_cli(["graph", "create", self.workflow_id])
        gpath = self._graph_path()
        data = {
            "graph": {
                "nodes": [
                    {"id": "a", "name": "A", "depends_on": ["nonexistent"], "status": "pending"},
                ],
                "parallelism": {"max_graph": 3, "max_agent": 1, "max_configured": None, "effective": 1}
            }
        }
        gpath.write_text(json.dumps(data, indent=2))
        ec, out, err = self._run_cli(["graph", "validate", self.workflow_id])
        self.assertNotEqual(ec, 0)
        self.assertIn("unknown", out.lower())


class TestDAGEngine(unittest.TestCase):
    """Direct tests for the ExecutionGraph Python class."""

    def _import_engine(self):
        """Import the ExecutionGraph class from the CLI script."""
        import importlib.util
        cli_path = Path(__file__).parent.parent / "cli" / "intent-first"
        loader = importlib.machinery.SourceFileLoader("intent_first_cli", str(cli_path))
        spec = importlib.util.spec_from_loader("intent_first_cli", loader)
        mod = importlib.util.module_from_spec(spec)
        # Prevent the module from running main() by patching sys.argv
        old_argv = sys.argv
        sys.argv = ["intent-first", "help"]
        try:
            spec.loader.exec_module(mod)
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv
        return mod.ExecutionGraph

    def test_ready_nodes_empty(self):
        EG = self._import_engine()
        g = EG()
        self.assertEqual(g.ready_nodes(), [])

    def test_ready_nodes_no_deps(self):
        EG = self._import_engine()
        g = EG()
        g.nodes = [
            {"id": "a", "depends_on": [], "status": "pending"},
            {"id": "b", "depends_on": [], "status": "pending"},
        ]
        ready = g.ready_nodes()
        self.assertEqual(len(ready), 2)

    def test_ready_nodes_with_deps(self):
        EG = self._import_engine()
        g = EG()
        g.nodes = [
            {"id": "a", "depends_on": [], "status": "complete"},
            {"id": "b", "depends_on": ["a"], "status": "pending"},
            {"id": "c", "depends_on": ["b"], "status": "pending"},
        ]
        ready = g.ready_nodes()
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0]["id"], "b")

    def test_topological_order(self):
        EG = self._import_engine()
        g = EG()
        g.nodes = [
            {"id": "c", "depends_on": ["b"]},
            {"id": "b", "depends_on": ["a"]},
            {"id": "a", "depends_on": []},
        ]
        order = g.topological_order()
        self.assertEqual(order, ["a", "b", "c"])

    def test_topological_order_parallel(self):
        EG = self._import_engine()
        g = EG()
        g.nodes = [
            {"id": "a", "depends_on": []},
            {"id": "b", "depends_on": []},
            {"id": "c", "depends_on": ["a", "b"]},
        ]
        order = g.topological_order()
        self.assertEqual(len(order), 3)
        self.assertIn("a", order[:2])
        self.assertIn("b", order[:2])
        self.assertEqual(order[2], "c")

    def test_cycle_detection(self):
        EG = self._import_engine()
        g = EG()
        g.nodes = [
            {"id": "a", "depends_on": ["c"]},
            {"id": "b", "depends_on": ["a"]},
            {"id": "c", "depends_on": ["b"]},
        ]
        issues = g.validate()
        self.assertTrue(any("cycle" in i.lower() for i in issues))

    def test_missing_dep_detection(self):
        EG = self._import_engine()
        g = EG()
        g.nodes = [
            {"id": "a", "depends_on": ["nonexistent"]},
        ]
        issues = g.validate()
        self.assertTrue(any("unknown" in i.lower() for i in issues))

    def test_fail_propagation(self):
        EG = self._import_engine()
        g = EG()
        g.nodes = [
            {"id": "a", "depends_on": [], "status": "complete"},
            {"id": "b", "depends_on": ["a"], "status": "in_progress"},
            {"id": "c", "depends_on": ["b"], "status": "pending"},
            {"id": "d", "depends_on": ["c"], "status": "pending"},
        ]
        g.fail_node("b")
        self.assertEqual(g.nodes[1]["status"], "failed")
        self.assertEqual(g.nodes[2]["status"], "blocked")
        self.assertEqual(g.nodes[3]["status"], "blocked")

    def test_progress_summary(self):
        EG = self._import_engine()
        g = EG()
        g.nodes = [
            {"id": "a", "status": "complete"},
            {"id": "b", "status": "in_progress"},
            {"id": "c", "status": "pending"},
            {"id": "d", "status": "failed"},
        ]
        summary = g.progress_summary()
        self.assertEqual(summary["complete"], 1)
        self.assertEqual(summary["in_progress"], 1)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["failed"], 1)

    def test_depth_map(self):
        EG = self._import_engine()
        g = EG()
        g.nodes = [
            {"id": "a", "depends_on": []},
            {"id": "b", "depends_on": ["a"]},
            {"id": "c", "depends_on": ["b"]},
        ]
        dm = g.depth_map()
        self.assertEqual(dm["a"], 0)
        self.assertEqual(dm["b"], 1)
        self.assertEqual(dm["c"], 2)

    def test_save_and_load(self):
        EG = self._import_engine()
        g = EG()
        g.nodes = [
            {"id": "a", "depends_on": [], "status": "pending"},
        ]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)
        try:
            g.save(path)
            g2 = EG.load(path)
            self.assertEqual(len(g2.nodes), 1)
            self.assertEqual(g2.nodes[0]["id"], "a")
        finally:
            path.unlink()


class TestSpawn(CLITestBase):
    """Tests for spawn command."""

    def test_spawn_basic(self):
        self._create_stage_files()
        ec, out, err = self._run_cli(["spawn", self.workflow_id, "child-1"])
        self.assertEqual(ec, 0, f"stderr: {err}")
        child_dir = Path(self.test_dir) / "workflows" / "child-1"
        self.assertTrue(child_dir.is_dir())
        # Check parent's spawned_workflows was updated
        parent_status = self.workflow_dir / "status.yml"
        content = parent_status.read_text()
        self.assertIn("child-1", content)

    def test_spawn_with_intent(self):
        self._create_stage_files()
        ec, out, err = self._run_cli([
            "spawn", self.workflow_id, "child-2", "--intent", "Add caching layer"
        ])
        self.assertEqual(ec, 0, f"stderr: {err}")
        intent_file = Path(self.test_dir) / "workflows" / "child-2" / "s1_intent.md"
        self.assertTrue(intent_file.is_file())
        self.assertIn("caching", intent_file.read_text().lower())

    def test_spawn_invalid_parent(self):
        ec, out, err = self._run_cli(["spawn", "nonexistent", "child-3"])
        self.assertNotEqual(ec, 0)


class TestLink(CLITestBase):
    """Tests for link command."""

    def test_link_basic(self):
        # Create a second workflow
        wf2_dir = Path(self.test_dir) / "workflows" / "test-2"
        wf2_dir.mkdir(parents=True, exist_ok=True)
        wf2_status = wf2_dir / "status.yml"
        wf2_status.write_text(f'workflow_id: "test-2"\nstages:\n  spec:\n    status: pending\n')

        ec, out, err = self._run_cli(["link", self.workflow_id, "test-2"])
        self.assertEqual(ec, 0, f"stderr: {err}")
        self.assertIn("related", out)

    def test_link_with_relation(self):
        wf2_dir = Path(self.test_dir) / "workflows" / "test-2"
        wf2_dir.mkdir(parents=True, exist_ok=True)
        wf2_status = wf2_dir / "status.yml"
        wf2_status.write_text(f'workflow_id: "test-2"\nstages:\n  spec:\n    status: pending\n')

        ec, out, err = self._run_cli(["link", self.workflow_id, "test-2", "--relation", "blocks"])
        self.assertEqual(ec, 0, f"stderr: {err}")
        self.assertIn("blocks", out)

    def test_link_invalid_relation(self):
        wf2_dir = Path(self.test_dir) / "workflows" / "test-2"
        wf2_dir.mkdir(parents=True, exist_ok=True)
        wf2_status = wf2_dir / "status.yml"
        wf2_status.write_text(f'workflow_id: "test-2"\nstages:\n  spec:\n    status: pending\n')

        ec, out, err = self._run_cli(["link", self.workflow_id, "test-2", "--relation", "invalid"])
        self.assertNotEqual(ec, 0)


class TestStatus(CLITestBase):
    """Tests for status command."""

    def test_status_all(self):
        self._create_stage_files()
        ec, out, err = self._run_cli(["status"])
        self.assertEqual(ec, 0, f"stderr: {err}")
        self.assertIn(self.workflow_id, out)

    def test_status_single_workflow(self):
        self._create_stage_files()
        ec, out, err = self._run_cli(["status", "--workflow", self.workflow_id])
        self.assertEqual(ec, 0, f"stderr: {err}")
        self.assertIn("Workflow:", out)
        self.assertIn("Stages:", out)

    def test_status_nonexistent_workflow(self):
        ec, out, err = self._run_cli(["status", "--workflow", "nonexistent"])
        self.assertNotEqual(ec, 0)


class TestBackwardCompatibility(CLITestBase):
    """Test that existing status-update commands still work with new status.yml format."""

    def test_status_update_with_phases_in_yml(self):
        """Test that status-update works when status.yml has phase blocks."""
        ec, out, err = self._run_cli([
            "status-update", self.workflow_id, "spec", "--status", "approved"
        ])
        self.assertEqual(ec, 0, f"stderr: {err}")

    def test_lock_with_phases_in_yml(self):
        """Test that lock works when status.yml has phase blocks."""
        self._create_stage_files()
        ec, out, err = self._run_cli(["lock", self.workflow_id, "spec"])
        self.assertEqual(ec, 0, f"stderr: {err}")


if __name__ == "__main__":
    unittest.main()
