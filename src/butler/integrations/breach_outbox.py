"""Consume privacy-classified breach events from Data Breach Scanner."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from butler.integrations.notifications import NotificationChannel

SAFE_ID = re.compile(r"^breach-[a-f0-9]{24}$")
SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


@dataclass(frozen=True, slots=True)
class ConsumeResult:
    delivered: int
    failed: int
    invalid: int
    pending: int


class PrivateBreachConsumer:
    def __init__(self, *, outbox_root: Path, notifier: NotificationChannel | None) -> None:
        self.pending_dir = outbox_root / "private"
        self.processed_dir = outbox_root / "processed" / "private"
        self.notifier = notifier

    def consume(self, *, dry_run: bool = False, limit: int = 20) -> ConsumeResult:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if not self.pending_dir.is_dir():
            return ConsumeResult(0, 0, 0, 0)
        delivered = failed = invalid = 0
        files = sorted(self.pending_dir.glob("*.json"))[:limit]
        for path in files:
            try:
                event = self._read_event(path)
            except (OSError, ValueError, json.JSONDecodeError):
                invalid += 1
                continue
            if dry_run:
                continue
            if self.notifier is None:
                raise RuntimeError("private breach delivery is not configured")
            message = self._format(event)
            if not self.notifier.notify(
                title="Butler — alerta de exposição",
                message=message,
            ):
                failed += 1
                continue
            self._complete(path)
            delivered += 1
        pending = len(list(self.pending_dir.glob("*.json")))
        return ConsumeResult(delivered, failed, invalid, pending)

    @staticmethod
    def _read_event(path: Path) -> dict[str, object]:
        if path.is_symlink() or path.stat().st_size > 64 * 1024:
            raise ValueError("unsafe event file")
        event = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(event, dict):
            raise ValueError("event must be an object")
        event_id = event.get("event_id")
        if (
            event.get("schema_version") != 1
            or event.get("classification") != "private"
            or not isinstance(event_id, str)
            or not SAFE_ID.fullmatch(event_id)
            or path.name != f"{event_id}.json"
            or event.get("severity") not in SEVERITIES
            or not isinstance(event.get("remediation"), list)
        ):
            raise ValueError("invalid private breach event")
        return event

    @staticmethod
    def _format(event: dict[str, object]) -> str:
        severity = str(event["severity"])
        icon = "🚨" if severity == "CRITICAL" else "⚠️"
        target = event.get("victim") or event.get("domain") or "identidade monitorizada"
        remediation = event.get("remediation")
        if not isinstance(remediation, list):
            remediation = []
        actions = [str(action)[:300] for action in remediation if isinstance(action, str)][:5]
        action_text = "\n".join(f"• {action}" for action in actions)
        return (
            f"{icon} {severity}: {str(event.get('title', 'Exposição'))[:200]}\n"
            f"Afetado: {str(target)[:200]}\n"
            f"Domínio: {str(event.get('domain') or '-')[:200]}\n"
            f"Confiança: {event.get('confidence', '-')}\n\n"
            f"Remediação:\n{action_text}"
        )[:3900]

    def _complete(self, path: Path) -> None:
        self.processed_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        destination = self.processed_dir / path.name
        if destination.exists():
            path.unlink()
            return
        os.replace(path, destination)
