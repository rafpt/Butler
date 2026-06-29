import json

from butler.integrations.breach_outbox import PrivateBreachConsumer


class Notifier:
    def __init__(self, result=True):
        self.result = result
        self.messages = []

    def notify(self, *, title, message):
        self.messages.append((title, message))
        return self.result


def event(event_id="breach-" + "a" * 24):
    return {
        "schema_version": 1,
        "classification": "private",
        "event_id": event_id,
        "title": "Credential exposure",
        "severity": "CRITICAL",
        "confidence": 95,
        "victim": "owner@example.com",
        "domain": "example.com",
        "remediation": ["Rotate password", "Enable MFA"],
    }


def write_event(root, payload):
    pending = root / "private"
    pending.mkdir(parents=True)
    path = pending / f"{payload['event_id']}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_delivers_then_moves_private_event(tmp_path):
    path = write_event(tmp_path, event())
    notifier = Notifier()
    result = PrivateBreachConsumer(
        outbox_root=tmp_path,
        notifier=notifier,
    ).consume()
    assert result.delivered == 1
    assert not path.exists()
    assert (tmp_path / "processed" / "private" / path.name).is_file()
    assert "owner@example.com" in notifier.messages[0][1]
    assert "Rotate password" in notifier.messages[0][1]


def test_failed_delivery_remains_pending(tmp_path):
    path = write_event(tmp_path, event())
    result = PrivateBreachConsumer(
        outbox_root=tmp_path,
        notifier=Notifier(False),
    ).consume()
    assert result.failed == 1
    assert path.is_file()


def test_rejects_public_event_in_private_outbox(tmp_path):
    payload = event()
    payload["classification"] = "public"
    path = write_event(tmp_path, payload)
    result = PrivateBreachConsumer(
        outbox_root=tmp_path,
        notifier=Notifier(),
    ).consume()
    assert result.invalid == 1
    assert path.is_file()
