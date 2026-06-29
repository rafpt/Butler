"""Central policy gate for user and automated actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Risk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Decision(StrEnum):
    ALLOW = "allow"
    REQUIRE_CONFIRMATION = "require_confirmation"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class ActionRequest:
    action: str
    risk: Risk
    reversible: bool
    initiated_by: str
    explicitly_approved: bool = False


@dataclass(frozen=True, slots=True)
class PolicyResult:
    decision: Decision
    reason: str


class AutonomyPolicy:
    """Four levels: observe, suggest, reversible action, bounded autonomy."""

    def __init__(self, level: int = 2) -> None:
        if level not in range(1, 5):
            raise ValueError("Autonomy level must be between 1 and 4")
        self.level = level

    def evaluate(self, request: ActionRequest) -> PolicyResult:
        if request.risk is Risk.CRITICAL:
            return PolicyResult(Decision.DENY, "Critical-risk actions are never autonomous")

        if request.initiated_by == "user" and request.explicitly_approved:
            return PolicyResult(Decision.ALLOW, "The user explicitly requested this action")

        if request.risk is Risk.HIGH or not request.reversible:
            return PolicyResult(
                Decision.REQUIRE_CONFIRMATION,
                "High-risk or irreversible actions require explicit confirmation",
            )

        if self.level < 3:
            return PolicyResult(
                Decision.REQUIRE_CONFIRMATION,
                "Autonomy level permits suggestions but not autonomous writes",
            )

        if request.risk is Risk.MEDIUM and self.level < 4:
            return PolicyResult(
                Decision.REQUIRE_CONFIRMATION,
                "Medium-risk actions require autonomy level 4",
            )

        return PolicyResult(Decision.ALLOW, "Action is within the configured autonomy boundary")
