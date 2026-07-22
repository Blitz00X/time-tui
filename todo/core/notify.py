"""
Desktop notification helper via the freedesktop.org Notifications spec.

Uses ``dbus-send`` to talk to ``org.freedesktop.Notifications`` on the
session bus, so the TUI doesn't depend on a ``notify-send`` binary or a
Python DBus binding. The notification daemon accepts a single DBus call
with a string body (summary).

If ``dbus-send`` is missing or the notification daemon is unreachable,
``notify()`` returns False and never raises.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Optional


log = logging.getLogger("time_tui.notify")

NOTIFICATIONS_SERVICE = "org.freedesktop.Notifications"
NOTIFICATIONS_PATH = "/org/freedesktop/Notifications"
NOTIFICATIONS_IFACE = "org.freedesktop.Notifications"


# FreeDesktop Notifications "Notify" signature is
#   s app_name, u replaces_id, s app_icon, s summary, s body,
#   as actions, a{sv} hints, u expire_timeout
# We use a JSON string in the summary slot to keep dbus-send happy with
# simple type=string arguments.

def notify(
    summary: str,
    body: str = "",
    *,
    urgency: str = "normal",
    timeout_ms: int = 5000,
    app_name: str = "time-tui",
) -> bool:
    """Show a desktop notification.

    ``urgency`` is one of ``"low"``, ``"normal"``, ``"critical"``. Returns
    True on success, False if the notification daemon is unreachable.
    """
    binary = shutil.which("dbus-send")
    if binary is None:
        log.debug("notifications: dbus-send not installed")
        return False
    try:
        payload = json.dumps({
            "summary": summary,
            "body": body,
            "urgency": urgency,
            "app": app_name,
        })
        result = subprocess.run(
            [
                binary,
                "--session",
                "--dest=" + NOTIFICATIONS_SERVICE,
                "--type=method_call",
                NOTIFICATIONS_PATH,
                f"{NOTIFICATIONS_IFACE}.Notify",
                f"string:{app_name}",
                "uint32:0",
                "string:",
                f"string:{summary}",
                f"string:{body}",
                "array:string:",
                "dict:string:variant:",
                f"int32:{timeout_ms}",
            ],
            capture_output=True,
            timeout=2.0,
        )
        return result.returncode == 0
    except Exception as exc:
        log.debug("notifications: dbus-send failed: %s", exc)
        return False


__all__ = ["notify"]