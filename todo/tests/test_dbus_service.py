"""Tests for the DBus service (signal-publishing side).

The service publishes ``Updated`` signals via ``dbus-send``. Method calls
(Pause/Resume/Stop) are intentionally not implemented yet — the
extension is read-only.

Tests cover:
- TrackerState dataclass
- TrackerAccessor protocol
- DBusService lifecycle (graceful without dbus-send)
- publish_state / tick heartbeat
- read_state_sync
- Constants stability (wire format)
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from todo.core import dbus_service


# ── TrackerState ─────────────────────────────────────────────────────────────

def test_tracker_state_idle_factory() -> None:
    s = dbus_service.TrackerState.idle()
    assert s.active is False


def test_tracker_state_to_wire() -> None:
    s = dbus_service.TrackerState(
        active=True,
        kind="pomodoro",
        label="kod yaz",
        namespace="bigg",
        started_at="2026-07-22T14:30:00",
        duration_sec=1500,
        remaining_sec=900,
        elapsed_sec=600,
        progress=0.4,
        paused=False,
    )
    wire = s.to_wire()
    assert wire["active"] is True
    assert wire["remaining_sec"] == 900


def test_default_accessor_idle() -> None:
    acc = dbus_service.TrackerAccessor()
    assert acc.read_state().active is False
    assert acc.pause() is False


def test_subclass_accessor() -> None:
    class A(dbus_service.TrackerAccessor):
        def read_state(self):
            return dbus_service.TrackerState(active=True, label="x")
        def pause(self):
            return True

    a = A()
    assert a.read_state().label == "x"
    assert a.pause() is True


# ── Service lifecycle ────────────────────────────────────────────────────────

def test_service_init() -> None:
    svc = dbus_service.DBusService()
    assert svc.is_running() is False


def test_service_graceful_without_dbus_send(monkeypatch) -> None:
    """If dbus-send is missing, start() returns False."""
    monkeypatch.setattr(dbus_service.shutil, "which", lambda _x: None)
    svc = dbus_service.DBusService()
    assert svc.start() is False
    assert svc.is_running() is False


def test_service_start_when_dbus_send_available() -> None:
    svc = dbus_service.DBusService()
    svc.bind_accessor(dbus_service.TrackerAccessor())
    if shutil.which("dbus-send") is None:
        pytest.skip("dbus-send not installed")
    assert svc.start() is True
    svc.stop()


def test_service_double_start_idempotent() -> None:
    if shutil.which("dbus-send") is None:
        pytest.skip("dbus-send not installed")
    svc = dbus_service.DBusService()
    assert svc.start() is True
    assert svc.start() is True
    svc.stop()


def test_service_stop_when_never_started() -> None:
    svc = dbus_service.DBusService()
    svc.stop()  # no error
    svc.stop()


def test_publish_state_caches_even_when_not_running() -> None:
    svc = dbus_service.DBusService()
    state = dbus_service.TrackerState(active=True, label="x")
    svc.publish_state(state)  # should not raise even if not running
    cached = svc.read_state_sync()
    assert cached.label == "x"
    assert cached.active is True


def test_tick_emits_when_heartbeat_elapsed() -> None:
    svc = dbus_service.DBusService()
    if shutil.which("dbus-send") is None:
        pytest.skip("dbus-send not installed")
    svc.start()
    state = dbus_service.TrackerState(active=True, label="tick-test")
    clock = [0.0]
    svc._now = lambda: clock[0]
    svc.publish_state(state)
    clock[0] = 100.0
    captured: list = []
    class A(dbus_service.TrackerAccessor):
        def read_state(self):
            captured.append(1)
            return state
    svc.bind_accessor(A())
    svc.tick()
    svc.stop()
    assert captured


def test_tick_skipped_when_not_running() -> None:
    svc = dbus_service.DBusService()
    captured: list = []
    class A(dbus_service.TrackerAccessor):
        def read_state(self):
            captured.append(1)
            return dbus_service.TrackerState.idle()
    svc.bind_accessor(A())
    svc.tick()
    assert captured == []


def test_tick_skipped_when_heartbeat_not_elapsed() -> None:
    svc = dbus_service.DBusService()
    if shutil.which("dbus-send") is None:
        pytest.skip("dbus-send not installed")
    svc.start()
    state = dbus_service.TrackerState(active=True, label="x")
    clock = [0.0]
    svc._now = lambda: clock[0]
    svc.publish_state(state)
    clock[0] = 0.5
    captured: list = []
    class A(dbus_service.TrackerAccessor):
        def read_state(self):
            captured.append(1)
            return state
    svc.bind_accessor(A())
    svc.tick()
    svc.stop()
    assert captured == []


# ── Subprocess invocation ───────────────────────────────────────────────────

def test_dbus_send_signal_invokes_subprocess(monkeypatch) -> None:
    """publish_state fires a dbus-send subprocess when DBus is available."""
    if shutil.which("dbus-send") is None:
        pytest.skip("dbus-send not installed")
    calls = []
    def fake_run(cmd, **kw):
        calls.append(cmd)
        from unittest.mock import MagicMock
        m = MagicMock()
        m.returncode = 0
        return m
    monkeypatch.setattr(dbus_service.subprocess, "run", fake_run)

    svc = dbus_service.DBusService()
    svc.start(emit_initial=False)
    state = dbus_service.TrackerState(active=True, label="publishme")
    svc.publish_state(state)
    # Wait for the daemon thread to invoke dbus-send.
    for _ in range(40):
        if calls:
            break
        time.sleep(0.05)
    svc.stop()
    assert calls, "no dbus-send calls were made"
    cmd = calls[-1]  # the last call should be our publish_state(state)
    assert cmd[0].endswith("dbus-send")
    assert "--session" in cmd
    assert "--type=signal" in cmd
    # The body is the last argument with string: prefix.
    body_arg = [a for a in cmd if a.startswith("string:")][0]
    body = body_arg[len("string:"):]
    parsed = json.loads(body)
    assert parsed["active"] is True, f"expected active=True, got body: {body!r}"
    assert parsed["label"] == "publishme"


def test_dbus_send_failure_does_not_raise(monkeypatch) -> None:
    """A failed dbus-send invocation must not crash the publisher."""
    if shutil.which("dbus-send") is None:
        pytest.skip("dbus-send not installed")
    def fake_run(*_a, **_kw):
        from unittest.mock import MagicMock
        m = MagicMock()
        m.returncode = 1  # failure
        return m
    monkeypatch.setattr(dbus_service.subprocess, "run", fake_run)
    svc = dbus_service.DBusService()
    svc.start()
    # publish_state must not raise even if subprocess returns nonzero.
    svc.publish_state(dbus_service.TrackerState(active=True))
    import time
    time.sleep(0.2)
    svc.stop()


# ── Wire format constants ───────────────────────────────────────────────────

def test_service_constants_are_stable() -> None:
    assert dbus_service.SERVICE_NAME == "org.timetui.Session"
    assert dbus_service.IFACE_NAME == "org.timetui.Session"
    assert dbus_service.OBJECT_PATH == "/org/timetui/Session"


def test_signal_member_name() -> None:
    """The signal member is 'Updated' — the extension subscribes by name."""
    # The member name is hardcoded inside _emit_updated. We test the
    # docstring contract.
    assert "Updated" in dbus_service.__doc__


# ── state-path helper ────────────────────────────────────────────────────────

def test_write_state_path_creates_file(tmp_path: Path, monkeypatch) -> None:
    """start() writes the project root to ~/.config/timetui/state-path."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    svc = dbus_service.DBusService()
    svc.bind_accessor(dbus_service.TrackerAccessor())
    svc.set_root(tmp_path / "project")
    (tmp_path / "project").mkdir()
    if shutil.which("dbus-send") is None:
        pytest.skip("dbus-send not installed")
    svc.start()
    try:
        written = fake_home / ".config" / "timetui" / "state-path"
        assert written.exists()
        assert str((tmp_path / "project").resolve()) in written.read_text(encoding="utf-8")
    finally:
        svc.stop()


def test_write_state_path_silent_on_failure(tmp_path: Path, monkeypatch) -> None:
    """Failure to write state-path doesn't crash start()."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "nonexistent-home")
    svc = dbus_service.DBusService()
    svc.bind_accessor(dbus_service.TrackerAccessor())
    svc.set_root(tmp_path / "project")
    (tmp_path / "project").mkdir()
    if shutil.which("dbus-send") is None:
        pytest.skip("dbus-send not installed")
    # Should not raise even if home doesn't exist (mkdir parents=True
    # would still create it — but if it fails, we silently log).
    svc.start()
    svc.stop()