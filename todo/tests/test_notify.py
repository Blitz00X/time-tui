"""Unit tests for the desktop notification helper (dbus-send based)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from todo.core import notify


def test_notify_returns_false_when_dbus_send_missing(monkeypatch) -> None:
    """If dbus-send isn't installed, notify() returns False without raising."""
    monkeypatch.setattr(notify.shutil, "which", lambda _x: None)
    assert notify.notify("hello") is False


def test_notify_sends_correct_command(monkeypatch) -> None:
    """Verify the dbus-send invocation carries the right args."""
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        from unittest.mock import MagicMock
        m = MagicMock()
        m.returncode = 0
        return m

    monkeypatch.setattr(notify.shutil, "which", lambda _x: "/usr/bin/dbus-send")
    monkeypatch.setattr(notify.subprocess, "run", fake_run)

    result = notify.notify("pomodoro done", "good work!", urgency="normal", timeout_ms=3000)
    assert result is True
    assert calls, "dbus-send should have been called"
    cmd = calls[0]
    assert "dbus-send" in cmd[0]
    assert "--session" in cmd
    assert "--dest=org.freedesktop.Notifications" in cmd
    assert any(a.startswith("string:pomodoro done") for a in cmd)
    assert any(a.startswith("string:good work!") for a in cmd)


def test_notify_returns_false_on_subprocess_failure(monkeypatch) -> None:
    """If dbus-send returns nonzero, notify() returns False."""
    def fake_run(*_a, **_kw):
        from unittest.mock import MagicMock
        m = MagicMock()
        m.returncode = 1
        return m

    monkeypatch.setattr(notify.shutil, "which", lambda _x: "/usr/bin/dbus-send")
    monkeypatch.setattr(notify.subprocess, "run", fake_run)
    assert notify.notify("test") is False


def test_notify_handles_subprocess_exception(monkeypatch) -> None:
    """If dbus-send raises, notify() returns False."""
    def boom(*_a, **_kw):
        raise OSError("nope")

    monkeypatch.setattr(notify.shutil, "which", lambda _x: "/usr/bin/dbus-send")
    monkeypatch.setattr(notify.subprocess, "run", boom)
    assert notify.notify("test") is False


def test_notify_handles_timeout(monkeypatch) -> None:
    """A timeout from subprocess.run doesn't crash the caller."""
    def fake_run(*_a, **_kw):
        import subprocess
        raise subprocess.TimeoutExpired(cmd="dbus-send", timeout=2.0)

    monkeypatch.setattr(notify.shutil, "which", lambda _x: "/usr/bin/dbus-send")
    monkeypatch.setattr(notify.subprocess, "run", fake_run)
    assert notify.notify("test") is False


def test_notify_app_name_default() -> None:
    """The default app name is 'time-tui'."""
    import inspect
    sig = inspect.signature(notify.notify)
    assert sig.parameters["app_name"].default == "time-tui"


def test_notify_urgency_passed_through(monkeypatch) -> None:
    """Urgency is informational — dbus-send accepts only summary/body,
    so this test just ensures the call doesn't crash with each value."""
    def fake_run(*_a, **_kw):
        from unittest.mock import MagicMock
        m = MagicMock()
        m.returncode = 0
        return m

    monkeypatch.setattr(notify.shutil, "which", lambda _x: "/usr/bin/dbus-send")
    monkeypatch.setattr(notify.subprocess, "run", fake_run)

    for u in ("low", "normal", "critical"):
        assert notify.notify("x", urgency=u) is True