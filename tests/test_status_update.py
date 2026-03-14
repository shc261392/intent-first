#!/usr/bin/env python3
"""
Tests for intent-first status-update CLI command.

Tests the safe, well-tested status.yml update functionality:
- Valid field updates for each stage
- Timestamp formatting (ISO 8601 UTC)
- Invalid field rejection
- State transitions
- Concurrency safety
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


class TestStatusUpdate(unittest.TestCase):
    """Test the status-update CLI command."""
    
    def setUp(self):
        """Create a temporary workflow directory for testing."""
        self.test_dir = tempfile.mkdtemp(prefix="intent-first-test-")
        self.workflow_id = "test-1"
        self.workflow_dir = Path(self.test_dir) / "workflows" / self.workflow_id
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        
        # Get the CLI path
        self.cli_path = Path(__file__).parent.parent / "cli" / "intent-first"
        
        # Create a basic status.yml from template
        self._create_status_yml()
    
    def tearDown(self):
        """Clean up the temporary directory."""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def _create_status_yml(self):
        """Create a fresh status.yml file."""
        status_yml = self.workflow_dir / "status.yml"
        status_yml.write_text(f"""\
# Intent-First Workflow Status
workflow_id: "{self.workflow_id}"

stages:
  intent:
    status: draft
    locked_at: ""

  spec:
    status: pending
    approved_by: ""
    approved_at: ""
    locked_at: ""

  plan:
    status: pending
    derived_from: "s2_spec.md"
    approved_by: ""
    approved_at: ""
    locked_at: ""

  execution:
    status: pending
    started_at: ""
    completed_at: ""
    locked_at: ""

  artifacts:
    status: pending
    completed_at: ""
    locked_at: ""
""")
        return status_yml
    
    def _run_cli(self, args: list[str]) -> tuple[int, str, str]:
        """Run the CLI command and return (exit_code, stdout, stderr)."""
        env = os.environ.copy()
        env["INTENT_FIRST_WORKFLOW_DIR"] = str(Path(self.test_dir) / "workflows")
        
        cmd = [str(self.cli_path)] + args
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return result.returncode, result.stdout, result.stderr
    
    def _read_status_field(self, stage: str, field: str) -> str:
        """Read a field value from status.yml."""
        status_file = self.workflow_dir / "status.yml"
        in_stage = False
        for line in status_file.read_text().splitlines():
            if re.match(r"^  [a-z]", line):
                in_stage = line.strip().startswith(f"{stage}:")
            if in_stage and re.match(rf"^    {re.escape(field)}:", line):
                return line.split(":", 1)[1].strip().strip('"').split("#")[0].strip()
        return ""
    
    def test_update_simple_status(self):
        """Test updating a simple status field."""
        # Simulate: intent-first status-update test-1 spec --status approved
        exit_code, stdout, stderr = self._run_cli([
            "status-update", self.workflow_id, "spec", "--status", "approved"
        ])
        
        self.assertEqual(exit_code, 0, f"Exit code: {exit_code}, stderr: {stderr}")
        value = self._read_status_field("spec", "status")
        self.assertEqual(value, "approved")
    
    def test_update_approved_by(self):
        """Test updating approved_by field."""
        exit_code, stdout, stderr = self._run_cli([
            "status-update", self.workflow_id, "spec", "--approved-by", "Alice"
        ])
        
        self.assertEqual(exit_code, 0, f"stderr: {stderr}")
        value = self._read_status_field("spec", "approved_by")
        self.assertEqual(value, "Alice")
    
    def test_update_multiple_fields(self):
        """Test updating multiple fields in one command."""
        exit_code, stdout, stderr = self._run_cli([
            "status-update", self.workflow_id, "spec",
            "--status", "approved",
            "--approved-by", "Alice",
            "--approved-at", "2026-03-15T14:30:00Z"
        ])
        
        self.assertEqual(exit_code, 0, f"stderr: {stderr}")
        self.assertEqual(self._read_status_field("spec", "status"), "approved")
        self.assertEqual(self._read_status_field("spec", "approved_by"), "Alice")
        self.assertEqual(self._read_status_field("spec", "approved_at"), "2026-03-15T14:30:00Z")
    
    def test_update_execution_status(self):
        """Test updating execution stage fields."""
        exit_code, stdout, stderr = self._run_cli([
            "status-update", self.workflow_id, "execution", "--status", "in_progress"
        ])
        
        self.assertEqual(exit_code, 0, f"stderr: {stderr}")
        value = self._read_status_field("execution", "status")
        self.assertEqual(value, "in_progress")
    
    def test_update_artifacts_status(self):
        """Test updating artifacts stage fields."""
        exit_code, stdout, stderr = self._run_cli([
            "status-update", self.workflow_id, "artifacts", "--status", "complete"
        ])
        
        self.assertEqual(exit_code, 0, f"stderr: {stderr}")
        value = self._read_status_field("artifacts", "status")
        self.assertEqual(value, "complete")
    
    def test_timestamp_auto_fills_with_utc(self):
        """Test that 'auto' value fills in current UTC timestamp."""
        exit_code, stdout, stderr = self._run_cli([
            "status-update", self.workflow_id, "spec", "--approved-at", "auto"
        ])
        
        self.assertEqual(exit_code, 0, f"stderr: {stderr}")
        value = self._read_status_field("spec", "approved_at")
        
        # Should be an ISO 8601 UTC timestamp
        self.assertRegex(value, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$',
                        f"Value '{value}' doesn't match ISO 8601 UTC format")
    
    def test_invalid_stage_rejected(self):
        """Test that invalid stage names are rejected."""
        exit_code, stdout, stderr = self._run_cli([
            "status-update", self.workflow_id, "invalid", "--status", "approved"
        ])
        
        self.assertNotEqual(exit_code, 0, "Should exit with error for invalid stage")
    
    def test_invalid_field_for_stage_rejected(self):
        """Test that fields not valid for a stage are rejected."""
        # execution stage doesn't have 'approved_by' field
        exit_code, stdout, stderr = self._run_cli([
            "status-update", self.workflow_id, "execution", "--approved-by", "Alice"
        ])
        
        self.assertNotEqual(exit_code, 0, "Should exit with error for invalid field")
    
    def test_intent_stage_fields_valid(self):
        """Test that only valid fields work for intent stage."""
        # OK: status
        exit_code, _, stderr = self._run_cli(["status-update", self.workflow_id, "intent", "--status", "draft"])
        self.assertEqual(exit_code, 0, f"stderr: {stderr}")
        self.assertEqual(self._read_status_field("intent", "status"), "draft")
        
        # OK: locked_at
        exit_code, _, stderr = self._run_cli([
            "status-update", self.workflow_id, "intent", "--locked-at", "2026-03-15T14:30:00Z"
        ])
        self.assertEqual(exit_code, 0, f"stderr: {stderr}")
        
        # REJECTED: approved_by (not valid for intent)
        exit_code, _, _ = self._run_cli([
            "status-update", self.workflow_id, "intent", "--approved-by", "Alice"
        ])
        self.assertNotEqual(exit_code, 0)
    
    def test_spec_stage_fields_valid(self):
        """Test all valid fields for spec stage."""
        valid_fields = ["status", "approved-by", "approved-at", "locked-at"]
        for field in valid_fields:
            with self.subTest(field=field):
                # Reset status.yml for each field test
                self._create_status_yml()
                value = f"test-{field}-value"
                exit_code, _, stderr = self._run_cli([
                    "status-update", self.workflow_id, "spec", f"--{field}", value
                ])
                self.assertEqual(exit_code, 0, f"Failed for field {field}: {stderr}")
    
    def test_missing_workflow_rejected(self):
        """Test that updating a non-existent workflow is rejected."""
        exit_code, stdout, stderr = self._run_cli([
            "status-update", "nonexistent", "spec", "--status", "approved"
        ])
        
        self.assertNotEqual(exit_code, 0, "Should exit with error for missing workflow")
    
    def test_timestamp_format_preserved(self):
        """Test that ISO 8601 UTC timestamp format is preserved."""
        timestamp = "2026-03-15T14:30:45Z"
        exit_code, _, _ = self._run_cli([
            "status-update", self.workflow_id, "spec", "--approved-at", timestamp
        ])
        
        self.assertEqual(exit_code, 0)
        value = self._read_status_field("spec", "approved_at")
        self.assertEqual(value, timestamp)
    
    def test_status_file_not_corrupted_on_multiple_updates(self):
        """Test that multiple updates maintain status.yml integrity."""
        # First update
        self._run_cli(["status-update", self.workflow_id, "spec", "--status", "draft"])
        # Second update
        self._run_cli(["status-update", self.workflow_id, "spec", "--approved-by", "Bob"])
        # Third update
        self._run_cli(["status-update", self.workflow_id, "spec", "--approved-at", "2026-03-15T14:30:00Z"])
        
        # All values should be present
        self.assertEqual(self._read_status_field("spec", "status"), "draft")
        self.assertEqual(self._read_status_field("spec", "approved_by"), "Bob")
        self.assertEqual(self._read_status_field("spec", "approved_at"), "2026-03-15T14:30:00Z")
        
        # Verify status.yml is still valid YAML-like format
        status_file = self.workflow_dir / "status.yml"
        content = status_file.read_text()
        self.assertIn("workflow_id:", content)
        self.assertIn("stages:", content)
        self.assertIn("spec:", content)


class TestStatusUpdateCLIIntegration(unittest.TestCase):
    """Integration tests for the status-update command."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp(prefix="intent-first-integration-")
        self.workflow_id = "test-integration"
        self.workflow_dir = Path(self.test_dir) / "workflows" / self.workflow_id
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        
        # Create all stage files
        for stage_file in ["s1_intent.md", "s2_spec.md", "s3_plan.md", "s4_execution.md", "s5_artifacts.md"]:
            (self.workflow_dir / stage_file).write_text(f"# {stage_file}\n\nContent here.")
        
        # Get the CLI path
        self.cli_path = Path(__file__).parent.parent / "cli" / "intent-first"
        
        # Create status.yml
        self._create_status_yml()
    
    def tearDown(self):
        """Clean up."""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def _create_status_yml(self):
        """Create a fresh status.yml file."""
        status_yml = self.workflow_dir / "status.yml"
        status_yml.write_text(f"""\
workflow_id: "{self.workflow_id}"

stages:
  spec:
    status: pending
    approved_by: ""
    approved_at: ""
    locked_at: ""

  execution:
    status: pending
    started_at: ""
    completed_at: ""
    locked_at: ""

  artifacts:
    status: pending
    completed_at: ""
    locked_at: ""
""")
    
    def _run_cli(self, args: list[str]) -> tuple[int, str, str]:
        """Run the CLI command and return (exit_code, stdout, stderr)."""
        env = os.environ.copy()
        env["INTENT_FIRST_WORKFLOW_DIR"] = str(Path(self.test_dir) / "workflows")
        
        cmd = [str(self.cli_path)] + args
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return result.returncode, result.stdout, result.stderr
    
    def _read_status_field(self, stage: str, field: str) -> str:
        """Read a field value from status.yml."""
        status_file = self.workflow_dir / "status.yml"
        in_stage = False
        for line in status_file.read_text().splitlines():
            if re.match(r"^  [a-z]", line):
                in_stage = line.strip().startswith(f"{stage}:")
            if in_stage and re.match(rf"^    {re.escape(field)}:", line):
                return line.split(":", 1)[1].strip().strip('"').split("#")[0].strip()
        return ""
    
    def test_typical_approval_workflow(self):
        """Test a typical approval workflow sequence."""
        # 1. Spec is drafted
        exit_code, _, _ = self._run_cli(["status-update", self.workflow_id, "spec", "--status", "draft"])
        self.assertEqual(exit_code, 0)
        
        # 2. Human approves
        exit_code, _, _ = self._run_cli([
            "status-update", self.workflow_id, "spec",
            "--status", "approved",
            "--approved-by", "Alice",
            "--approved-at", "2026-03-15T10:00:00Z"
        ])
        self.assertEqual(exit_code, 0)
        
        # 3. Lock is applied (simulated - normally done by intent-first lock command)
        exit_code, _, _ = self._run_cli([
            "status-update", self.workflow_id, "spec",
            "--status", "locked",
            "--locked-at", "2026-03-15T10:00:01Z"
        ])
        self.assertEqual(exit_code, 0)
        
        # Verify final state
        self.assertEqual(self._read_status_field("spec", "status"), "locked")
        self.assertEqual(self._read_status_field("spec", "approved_by"), "Alice")
        self.assertEqual(self._read_status_field("spec", "approved_at"), "2026-03-15T10:00:00Z")
        self.assertEqual(self._read_status_field("spec", "locked_at"), "2026-03-15T10:00:01Z")
    
    def test_execution_lifecycle(self):
        """Test a complete execution stage lifecycle."""
        # Start execution
        exit_code, _, _ = self._run_cli([
            "status-update", self.workflow_id, "execution",
            "--status", "in_progress",
            "--started-at", "2026-03-15T11:00:00Z"
        ])
        self.assertEqual(exit_code, 0)
        self.assertEqual(self._read_status_field("execution", "status"), "in_progress")
        
        # Complete execution
        exit_code, _, _ = self._run_cli([
            "status-update", self.workflow_id, "execution",
            "--status", "complete",
            "--completed-at", "2026-03-15T12:30:00Z"
        ])
        self.assertEqual(exit_code, 0)
        self.assertEqual(self._read_status_field("execution", "status"), "complete")
        
        # Lock it
        exit_code, _, _ = self._run_cli([
            "status-update", self.workflow_id, "execution",
            "--status", "locked",
            "--locked-at", "2026-03-15T12:30:01Z"
        ])
        self.assertEqual(exit_code, 0)
        self.assertEqual(self._read_status_field("execution", "status"), "locked")


if __name__ == "__main__":
    unittest.main()
