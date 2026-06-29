"""Skills describe workflows; they do not own infrastructure."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    name: str
    description: str
    required_tools: tuple[str, ...] = ()


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition) -> None:
        if skill.name in self._skills:
            raise ValueError(f"Skill already registered: {skill.name}")
        self._skills[skill.name] = skill

    def get(self, name: str) -> SkillDefinition:
        try:
            return self._skills[name]
        except KeyError as error:
            raise KeyError(f"Unknown skill: {name}") from error
