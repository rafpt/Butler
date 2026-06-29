"""Boundary model for n8n; workflow payloads do not enter the domain directly."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class AutomationEnvelope:
    workflow: str
    event: str
    payload: dict[str, Any]
    correlation_id: str = field(default_factory=lambda: f"run_{uuid4().hex[:12]}")

    @classmethod
    def from_payload(cls, value: dict[str, Any]) -> AutomationEnvelope:
        workflow = str(value.get("workflow", "")).strip()
        event = str(value.get("event", "")).strip()
        payload = value.get("payload", {})
        if not workflow or not event:
            raise ValueError("workflow and event are required")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        return cls(workflow=workflow, event=event, payload=payload)
