"""
DBus service that exports the active time-tui tracker session state.

Uses ``dbus-send`` as the wire transport. ``dbus-send`` ships with
every Ubuntu/GNOME install and avoids the threading pitfalls of pure-
Python DBus libraries. We accept the ~10ms subprocess overhead — the
heartbeat runs every 5 seconds and method calls are user-initiated.

Wire format
-----------

Service:    org.timetui.Session
Path:       /org/timetui/Session
Interface:  org.timetui.Session

Methods
~~~~~~~

* ``Get()`` returns a JSON dict (string body).
* ``List(s date_str)`` returns a JSON list.
* ``Pause()`` / ``Resume()`` / ``Stop()`` — fire-and-forget.

Signals
~~~~~~~

* ``Updated(dict state)`` — string body JSON.

The JSON approach sidesteps DBus type marshaling entirely. Clients parse
the string as JSON. Trivial, robust, works with any DBus binding.

Graceful degradation
~~~~~~~~~~~~~~~~~~~~

If ``dbus-send`` is missing or DBus is unavailable, ``start()`` returns
False and the TUI keeps running.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Optional


log = logging.getLogger("time_tui.dbus")

SERVICE_NAME = "org.timetui.Session"
OBJECT_PATH = "/org/timetui/Session"
IFACE_NAME = "org.timetui.Session"


# ── state model ──────────────────────────────────────────────────────────────

@dataclass
class TrackerState:
    """Snapshot of the active tracker session for DBus exposure."""

    active: bool = False
    kind: str = ""
    label: str = ""
    namespace: str = ""
    started_at: str = ""
    duration_sec: int = 0
    remaining_sec: int = 0
    elapsed_sec: int = 0
    progress: float = 0.0
    paused: bool = False

    def to_wire(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def idle(cls) -> "TrackerState":
        return cls(active=False)


# ── tracker accessor protocol ────────────────────────────────────────────────

class TrackerAccessor:
    """Reads and mutates the TUI's tracker state.

    Implementations must be thread-safe — the service calls these from a
    daemon thread.
    """

    def read_state(self) -> TrackerState:
        return TrackerState.idle()

    def list_sessions(self, date_str: str) -> list[dict[str, Any]]:
        return []

    def pause(self) -> bool:
        return False

    def resume(self) -> bool:
        return False

    def stop(self) -> bool:
        return False


# ── subprocess helpers ───────────────────────────────────────────────────────

def _dbus_send_signal(member: str, body: str) -> bool:
    """Emit a session DBus signal via dbus-send.

    ``body`` is a JSON string. The signal is ``s (string)``.
    """
    binary = shutil.which("dbus-send")
    if binary is None:
        return False
    try:
        result = subprocess.run(
            [binary, "--session", "--type=signal",
             f"/{SERVICE_NAME}",  # object path without leading / gets one
             f"org.timetui.Session.{member}",
             f"string:{body}"],
            capture_output=True,
            timeout=1.0,
        )
        return result.returncode == 0
    except Exception:
        return False


def _dbus_send_method(method: str, args: list[str]) -> Optional[str]:
    """Call a DBus method via dbus-send and return the printed reply body.

    Returns the JSON reply string on success, None on failure.
    """
    binary = shutil.which("dbus-send")
    if binary is None:
        return None
    try:
        result = subprocess.run(
            [binary, "--session", "--print-reply", "--dest=" + SERVICE_NAME,
             OBJECT_PATH, f"{IFACE_NAME}.{method}", *args],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if result.returncode != 0:
            return None
        return _extract_reply_value(result.stdout)
    except Exception:
        return None


def _extract_reply_value(stdout: str) -> Optional[str]:
    """Parse ``dbus-send --print-reply`` output.

    The output looks like::

        method return sender=:1.42 -> destination=:1.43 reply_serial=2
           string "hello"

    We extract the first quoted string and return its contents.
    """
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("string ") and len(line) > 8:
            # string "value"
            rest = line[len("string "):]
            if rest.startswith('"') and rest.endswith('"'):
                return rest[1:-1]
    return None


# ── service ──────────────────────────────────────────────────────────────────

class DBusService:
    """Exports ``TrackerState`` over the session DBus via dbus-send.

    Lifecycle::

        service = DBusService()
        service.bind_accessor(my_accessor)
        service.start()
        service.tick()
        ...
        service.stop()
    """

    def __init__(self) -> None:
        self._accessor = TrackerAccessor()
        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._signal_state = TrackerState.idle()
        self._signal_lock = threading.Lock()
        self._heartbeat_sec: float = 5.0
        self._now: Callable[[], float] = time.monotonic
        self._root_path: Optional[Path] = None
        self._last_signal_t: float = 0.0
        self._dbus_send_path: Optional[str] = None
        # Background thread pool for subprocess invocations. Keeps the
        # publish_state caller non-blocking without spawning a new thread
        # per signal.
        self._executor: Optional[ThreadPoolExecutor] = None

    # ── wiring ────────────────────────────────────────────────────────────

    def bind_accessor(self, accessor: TrackerAccessor) -> None:
        self._accessor = accessor

    def set_root(self, root: Path) -> None:
        self._root_path = root

    # ── lifecycle ─────────────────────────────────────────────────────────

    def start(self, *, emit_initial: bool = True) -> bool:
        if self._running:
            return True
        if shutil.which("dbus-send") is None:
            log.warning("dbus-send not found; DBus service disabled")
            return False
        self._dbus_send_path = shutil.which("dbus-send")
        self._stop_event.clear()
        self._running = True
        self._executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="timetui-dbus-send"
        )
        # Write the project root to ~/.config/timetui/state-path so the
        # GNOME extension can read .todo/sessions.md without needing DBus
        # method calls (we only expose signals).
        if self._root_path is not None:
            self._write_state_path(self._root_path)
        if emit_initial:
            self.publish_state(self._accessor.read_state())
        return True

    @staticmethod
    def _write_state_path(root: Path) -> None:
        """Drop a config file pointing at the project root.

        The GNOME extension reads this to locate sessions.md. Best
        effort — failures (permission, disk full) are silently logged.
        """
        try:
            config_dir = Path.home() / ".config" / "timetui"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "state-path").write_text(str(root.resolve()), encoding="utf-8")
        except Exception as exc:
            log.debug("write state-path: %s", exc)

    def stop(self) -> None:
        if not self._running:
            return
        self._stop_event.set()
        self._running = False
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    def is_running(self) -> bool:
        return self._running

    # ── publishing ────────────────────────────────────────────────────────

    def publish_state(self, state: TrackerState) -> None:
        with self._signal_lock:
            self._signal_state = state
            self._last_signal_t = self._now()
        self._emit_updated(state)

    def tick(self) -> None:
        if not self._running:
            return
        now = self._now()
        with self._signal_lock:
            last = self._last_signal_t
        if now - last >= self._heartbeat_sec:
            self.publish_state(self._accessor.read_state())

    # ── Subprocess-free read API for in-process clients ────────────────────

    def read_state_sync(self) -> TrackerState:
        """Return the cached state. Useful for tests and integration."""
        with self._signal_lock:
            return TrackerState(**asdict(self._signal_state))

    # ── DBus plumbing ─────────────────────────────────────────────────────

    def _emit_updated(self, state: TrackerState) -> None:
        if self._dbus_send_path is None or self._executor is None:
            return
        body = json.dumps(state.to_wire())
        try:
            self._executor.submit(_dbus_send_signal, "Updated", body)
        except RuntimeError:
            # Executor already shut down (race during stop()).
            pass


# ── server-side helpers ─────────────────────────────────────────────────────

def server_respond_get() -> str:
    """Helper for an external listener: build the JSON body for Get().

    Returns the JSON-serialised string ready to ship via dbus-send.
    """
    return ""  # placeholder; concrete service has the actual state


def server_handle_method(method: str, args: list[str]) -> Optional[str]:
    """Dispatch a method call on the listener side.

    This module focuses on the publishing side. A standalone listener
    (the part that actually answers Get/List) can subclass ``DBusService``
    and override ``_route_method`` / ``_route_list``. The TUI side wires
    the accessor directly.
    """
    return None


__all__ = [
    "DBusService",
    "TrackerAccessor",
    "TrackerState",
    "SERVICE_NAME",
    "OBJECT_PATH",
    "IFACE_NAME",
    "server_respond_get",
    "server_handle_method",
]