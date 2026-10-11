"""Lint the shipped skills and templates: Agent Skills spec, token budget, tool neutrality, CLI references."""

from __future__ import annotations

import re
import unittest

from helpers import ProjectTestCase
from intent_first import adapters, cli
from intent_first.state import REQUIRED_SECTIONS, STAGES, parse_sections

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_WORDS = 500  # per skill body; keeps each stage under ~1k tokens
TOOL_SPECIFIC = re.compile(r"#tool:|vscode/|askQuestions|runInTerminal|copilot-instructions", re.I)


def frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert m, "missing YAML frontmatter"
    fields = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        fields[k.strip()] = v.strip()
    return fields, m.group(2)


class SkillsTest(unittest.TestCase):
    def test_agent_skills_spec(self):
        for name in adapters.SKILLS:
            with self.subTest(skill=name):
                fields, body = frontmatter(adapters.asset(f"skills/{name}/SKILL.md"))
                self.assertEqual(fields["name"], name)
                self.assertRegex(name, NAME_RE)
                self.assertLessEqual(len(name), 64)
                self.assertTrue(1 <= len(fields["description"]) <= 1024)
                self.assertTrue(set(fields) <= {"name", "description", "license", "compatibility", "metadata", "allowed-tools"})
                self.assertLessEqual(len(body.split()), MAX_WORDS)
                self.assertIsNone(TOOL_SPECIFIC.search(body), "skills must stay tool-neutral")

    def test_cli_commands_in_skills_exist(self):
        parser = cli.build_parser()
        commands = set(parser._subparsers._group_actions[0].choices)  # type: ignore[union-attr]
        texts = [adapters.asset(f"skills/{n}/SKILL.md") for n in adapters.SKILLS] + [adapters.asset("agents-block.md")]
        for text in texts:
            for cmd in re.findall(r"intent-first ([a-z]+)", text):
                self.assertIn(cmd, commands)

    def test_always_on_block_is_small(self):
        self.assertLessEqual(len(adapters.asset("agents-block.md").split()), 150)


class TemplatesTest(ProjectTestCase):
    def test_templates_have_required_sections_and_no_content(self):
        for stage in STAGES:
            with self.subTest(stage=stage):
                sections = parse_sections(adapters.asset(f"templates/{stage}.md"))
                required, _ = REQUIRED_SECTIONS[stage]
                for name in required:
                    self.assertIn(name.lower(), sections)
                self.assertTrue(all(not body for body in sections.values()), "guidance belongs in comments")


if __name__ == "__main__":
    unittest.main()


class SchemaTest(ProjectTestCase):
    """state.json written by the CLI matches the documented schema's required keys and enums."""

    def test_state_matches_schema(self):
        import json
        from pathlib import Path

        schema = json.loads((Path(__file__).resolve().parent.parent / "spec/state.schema.json").read_text())
        self.run_cli("new", "w")
        self.run_cli("graph", "add", "w", "n1")
        state = self.state("w")
        for key in schema["required"]:
            self.assertIn(key, state)
        self.assertEqual(state["schema_version"], schema["properties"]["schema_version"]["const"])
        self.assertEqual(set(state["stages"]), set(schema["properties"]["stages"]["required"]))
        for stage in state["stages"].values():
            for key in schema["$defs"]["stage"]["required"]:
                self.assertIn(key, stage)
        node = state["graph"]["nodes"][0]
        for key in schema["$defs"]["node"]["required"]:
            self.assertIn(key, node)
        self.assertIn(node["status"], schema["$defs"]["node"]["properties"]["status"]["enum"])
