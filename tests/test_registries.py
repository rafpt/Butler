import unittest
from dataclasses import dataclass
from typing import Any

from butler.policies.autonomy import Risk
from butler.skills import SkillDefinition, SkillRegistry
from butler.tools import ToolRegistry


@dataclass
class FakeTool:
    name: str = "fake"
    description: str = "Test tool"
    risk: Risk = Risk.LOW
    reversible: bool = True

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return arguments


class RegistryTests(unittest.TestCase):
    def test_tool_registration_rejects_duplicates(self) -> None:
        registry = ToolRegistry()
        registry.register(FakeTool())
        self.assertEqual(registry.names(), ("fake",))
        with self.assertRaises(ValueError):
            registry.register(FakeTool())

    def test_skill_registration(self) -> None:
        registry = SkillRegistry()
        registry.register(SkillDefinition("daily-review", "Review the day", ("tasks",)))
        self.assertEqual(registry.get("daily-review").required_tools, ("tasks",))


if __name__ == "__main__":
    unittest.main()
