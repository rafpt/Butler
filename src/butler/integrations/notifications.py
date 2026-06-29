"""Notification channel composition."""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger("butler.integrations.notifications")


class NotificationChannel(Protocol):
    def notify(self, *, title: str, message: str) -> bool: ...


class CompositeNotifier:
    """Deliver to every configured channel without coupling their failures."""

    def __init__(self, *channels: NotificationChannel) -> None:
        self.channels = channels

    def notify(self, *, title: str, message: str) -> bool:
        delivered = False
        for channel in self.channels:
            try:
                delivered = channel.notify(title=title, message=message) or delivered
            except Exception as error:  # A notification must never block report publication.
                logger.warning(
                    "Notification channel failed: %s",
                    type(error).__name__,
                )
        return delivered
