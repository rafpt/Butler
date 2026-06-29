import json
import unittest
from urllib.request import Request

from butler.integrations.notifications import CompositeNotifier
from butler.integrations.telegram import TelegramNotifier, discover_telegram_chats


class RecordingChannel:
    def __init__(self, *, delivered: bool = True, fail: bool = False) -> None:
        self.delivered = delivered
        self.fail = fail
        self.messages: list[str] = []

    def notify(self, *, title: str, message: str) -> bool:
        if self.fail:
            raise RuntimeError("offline")
        self.messages.append(f"{title}: {message}")
        return self.delivered


class NotificationTests(unittest.TestCase):
    def test_telegram_sends_bounded_json_payload(self) -> None:
        captured: list[tuple[Request, float]] = []

        def transport(request: Request, timeout: float) -> int:
            captured.append((request, timeout))
            return 200

        notifier = TelegramNotifier(
            bot_token="secret-token",
            chat_id="123456",
            timeout_seconds=4.0,
            transport=transport,
        )

        self.assertTrue(notifier.notify(title="Radar", message="A" * 5000))
        self.assertEqual(len(captured), 1)
        request, timeout = captured[0]
        payload = json.loads(request.data or b"{}")
        self.assertEqual(timeout, 4.0)
        self.assertEqual(payload["chat_id"], "123456")
        self.assertLessEqual(len(payload["text"]), 4000)
        self.assertTrue(payload["disable_web_page_preview"])

    def test_telegram_non_success_status_is_isolated(self) -> None:
        notifier = TelegramNotifier(
            bot_token="secret-token",
            chat_id="123456",
            transport=lambda request, timeout: 429,
        )

        self.assertFalse(notifier.notify(title="Radar", message="ready"))

    def test_composite_delivers_to_remaining_channels_after_failure(self) -> None:
        failing = RecordingChannel(fail=True)
        working = RecordingChannel()

        delivered = CompositeNotifier(failing, working).notify(
            title="Radar",
            message="ready",
        )

        self.assertTrue(delivered)
        self.assertEqual(working.messages, ["Radar: ready"])

    def test_discovers_and_deduplicates_bot_chats(self) -> None:
        body = json.dumps(
            {
                "ok": True,
                "result": [
                    {
                        "message": {
                            "chat": {
                                "id": 123456,
                                "type": "private",
                                "first_name": "Rui",
                                "username": "raf",
                            }
                        }
                    },
                    {
                        "message": {
                            "chat": {
                                "id": 123456,
                                "type": "private",
                                "first_name": "Rui",
                                "username": "raf",
                            }
                        }
                    },
                ],
            }
        ).encode()

        chats = discover_telegram_chats(
            bot_token="secret-token",
            transport=lambda request, timeout: (200, body),
        )

        self.assertEqual(len(chats), 1)
        self.assertEqual(chats[0].id, "123456")
        self.assertEqual(chats[0].name, "Rui")


if __name__ == "__main__":
    unittest.main()
