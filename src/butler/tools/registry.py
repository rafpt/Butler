"""Explicit registry keeps tool execution discoverable and policy-gated."""

from __future__ import annotations

from typing import Any, Protocol

from butler.policies.autonomy import Risk


class Tool(Protocol):
    name: str
    description: str
    risk: Risk
    reversible: bool

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]: ...


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as error:
            raise KeyError(f"Unknown tool: {name}") from error

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))
