"""Low-risk macOS notification adapter."""

from __future__ import annotations

import logging
import platform
import subprocess

logger = logging.getLogger("butler.integrations.macos")


class MacNotifier:
    def notify(self, *, title: str, message: str) -> bool:
        if platform.system() != "Darwin":
            return False
        safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
        safe_message = message.replace("\\", "\\\\").replace('"', '\\"')
        script = f'display notification "{safe_message}" with title "{safe_title}"'
        try:
            subprocess.run(
                ["/usr/bin/osascript", "-e", script],
                check=True,
                capture_output=True,
                timeout=5,
            )
            return True
        except (OSError, subprocess.SubprocessError) as error:
            logger.warning("macOS notification failed: %s", error)
            return False
