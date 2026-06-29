"""Telegram Bot API notification adapter."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("butler.integrations.telegram")

TelegramTransport = Callable[[Request, float], int]
TelegramReadTransport = Callable[[Request, float], tuple[int, bytes]]


@dataclass(frozen=True, slots=True)
class TelegramChat:
    id: str
    kind: str
    name: str
    username: str


class TelegramNotifier:
    def __init__(
        self,
        *,
        bot_token: str,
        chat_id: str,
        bot_username: str = "Aspasia_4U_Bot",
        timeout_seconds: float = 10.0,
        transport: TelegramTransport | None = None,
    ) -> None:
        if not bot_token.strip() or not chat_id.strip():
            raise ValueError("Telegram requires both bot token and chat ID")
        self.bot_token = bot_token.strip()
        self.chat_id = chat_id.strip()
        self.bot_username = bot_username.removeprefix("@").strip()
        self.timeout_seconds = timeout_seconds
        self.transport = transport or self._send

    def notify(self, *, title: str, message: str) -> bool:
        text = f"{title}\n\n{message}".strip()
        if len(text) > 4000:
            text = f"{text[:3997]}..."
        payload = json.dumps(
            {
                "chat_id": self.chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        request = Request(
            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Butler-Cyber-Radar/1.0",
            },
            method="POST",
        )
        try:
            status = self.transport(request, self.timeout_seconds)
        except HTTPError as error:
            logger.warning("Telegram notification rejected: HTTP %s", error.code)
            return False
        except (URLError, TimeoutError, OSError) as error:
            logger.warning("Telegram notification failed: %s", type(error).__name__)
            return False
        if status != 200:
            logger.warning("Telegram notification rejected: HTTP %s", status)
            return False
        return True

    @staticmethod
    def _send(request: Request, timeout: float) -> int:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            return int(response.status)


def discover_telegram_chats(
    *,
    bot_token: str,
    timeout_seconds: float = 10.0,
    transport: TelegramReadTransport | None = None,
) -> list[TelegramChat]:
    """Return chats that have interacted with the bot without exposing the token."""
    if not bot_token.strip():
        raise ValueError("Telegram bot token is required")
    request = Request(
        f"https://api.telegram.org/bot{bot_token.strip()}/getUpdates?limit=20&timeout=0",
        headers={"User-Agent": "Butler-Cyber-Radar/1.0"},
        method="GET",
    )
    reader = transport or _read_response
    try:
        status, body = reader(request, timeout_seconds)
    except HTTPError as error:
        raise RuntimeError(f"Telegram recusou a descoberta: HTTP {error.code}") from None
    except (URLError, TimeoutError, OSError) as error:
        raise RuntimeError(f"Falha ao contactar o Telegram: {type(error).__name__}") from None
    if status != 200:
        raise RuntimeError(f"Telegram recusou a descoberta: HTTP {status}")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("Resposta inválida do Telegram") from error
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RuntimeError("Telegram não confirmou a descoberta de chats")

    chats: dict[str, TelegramChat] = {}
    results = payload.get("result")
    if not isinstance(results, list):
        return []
    for update in results:
        if not isinstance(update, dict):
            continue
        message = update.get("message") or update.get("channel_post")
        if not isinstance(message, dict):
            continue
        chat = message.get("chat")
        if not isinstance(chat, dict) or not isinstance(chat.get("id"), int):
            continue
        chat_id = str(chat["id"])
        name = " ".join(
            value
            for value in (chat.get("first_name"), chat.get("last_name"), chat.get("title"))
            if isinstance(value, str) and value
        )
        chats[chat_id] = TelegramChat(
            id=chat_id,
            kind=str(chat.get("type", "")),
            name=name,
            username=str(chat.get("username", "")),
        )
    return sorted(chats.values(), key=lambda chat: chat.id)


def _read_response(request: Request, timeout: float) -> tuple[int, bytes]:
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        return int(response.status), response.read(512 * 1024 + 1)[: 512 * 1024]
