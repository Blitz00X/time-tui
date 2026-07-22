# timetui-topbar — GNOME Shell Extension

Show the active `time-tui` tracker session in the GNOME top bar.

## What it does

- Subscribes to the `org.timetui.Session.Updated` signal published by the
  TUI via `dbus-send`. The signal body is a JSON string with the tracker
  state (see Wire format below).
- Renders `⏱ MM:SS  label` in the top bar (right side).
- Clicking opens a popup with today's session log read from
  `.todo/sessions.md` (via `~/.config/timetui/state-path` which the TUI
  writes when it starts).
- Silently shows `⏱ —` when the TUI isn't running.

The TUI is the source of truth. The extension is a passive viewer — it
never writes to disk or calls DBus methods.

## Install

```bash
./install.sh
```

This copies files into `~/.local/share/gnome-shell/extensions/timetui-topbar@kutay/`.

Then restart GNOME Shell and enable:

```bash
# X11: press Alt+F2, type `r`, Enter.
# Wayland: log out and back in.
gnome-extensions enable timetui-topbar@kutay
gnome-extensions list --enabled | grep timetui
```

## Uninstall

```bash
gnome-extensions disable timetui-topbar@kutay
rm -rf ~/.local/share/gnome-shell/extensions/timetui-topbar@kutay
```

## Troubleshooting

**Top bar shows nothing.** The extension failed to load. Run:

```bash
journalctl --user -b -f | grep -i timetui
```

Look for JavaScript errors or import failures.

**Top bar shows `⏱ —`.** The TUI isn't running, or DBus is unavailable.
Start the TUI and the label should update within 5 seconds.

**Popup shows "No active session" but TUI is running.** The signal
subscription is working but the TUI's state is `active: false`. Check
that you've started a tracker (pomodoro / stopwatch / timer) in the TUI.

**Popup shows no "today's sessions".** The TUI writes
`~/.config/timetui/state-path` on startup. If that file is missing or
points to a non-existent project, the extension can't find `sessions.md`.
Check that the file exists and contains a valid project root path.

**Monitor the signal manually to confirm the TUI is publishing:**

```bash
gdbus monitor --session --dest org.timetui.Session
```

You should see `/org/timetui/Session:org.timetui.Session.Updated` events
with a JSON string body, every ~5 seconds.

## Wire format

The TUI exports `org.timetui.Session` on the session DBus.

### Signal: `Updated(s body)`

`body` is a JSON string. Parsed as:

```json
{
    "active": true,
    "kind": "pomodoro",
    "label": "kod yaz",
    "namespace": "bigg",
    "started_at": "",
    "duration_sec": 1500,
    "remaining_sec": 723,
    "elapsed_sec": 777,
    "progress": 0.518,
    "paused": false
}
```

Emitted every 5 seconds as a heartbeat plus on every state transition
(start, pause, resume, stop, kind change).

### Method calls

The TUI exposes **only signals**, no methods. Pause/Resume/Stop from
the top bar popup is a v2 feature (will require a separate listener
process to receive DBus method calls).

## GNOME Shell versions

Targets 45/46/47. May need small adjustments for future releases.