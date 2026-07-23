# Known Issues

Issues tracked in this file (instead of GitHub Issues) until the repo
has a working `gh` CLI auth flow on Kutay's box. Each issue below should
eventually move to a GitHub Issue once push lands.

---

## Issue: GNOME top-bar extension enabled but label not visible

**Date:** 2026-07-22
**Status:** open
**Affects:** `extensions/timetui-topbar/` (commit 9005ad6)
**Severity:** high — feature is shipped but unusable

### Symptom

- `gnome-extensions info timetui-topbar@kutay` reports `State: ACTIVE`
  after `Alt+F2 → r` (GNOME Shell reload).
- `journalctl --user -b | grep timetui` shows no JS warnings or errors
  after reload.
- Top bar still shows `⏱ —` only, or no widget at all.
- No `timetui` signal observed in `gdbus monitor --session --dest
  org.timetui.Session` (could not verify directly — `gdbus monitor`
  commands were blocked by user).

### What was tried

1. **Legacy `imports.gi` syntax** → failed with
   `SyntaxError: import declarations may only appear at top level of a
   module @ extension.js:17:14`.
   Fix: rewrote as ESM (`import GObject from 'gi://Gobject'; ...`).

2. **9-arg `Gio.DBus.session.signal_subscribe`** → failed with
   `Too many arguments to method Gio.DBusConnection.signal_subscribe:
   expected 7, got 8`.
   Fix: removed the trailing `null` (user_data) argument.

3. **Reload** (Alt+F2 → r → Enter) followed by
   `gnome-extensions enable timetui-topbar@kutay`. State is now
   `ACTIVE` per `gnome-extensions info`.

### Likely causes (unverified)

1. **TUI never publishes** — `todotui`/`todo-tui` hasn't been launched
   since the extension went ACTIVE, so no `Updated` signal is emitted.
   The extension shows `⏱ —` because its renderer defaults to "no
   signal received" state.
2. **Signal subscribe filter mismatch** — GNOME 46 GJS may have a
   different signature for `signal_subscribe` than what we call. The
   "expected 7, got 8" message suggests the wrapper exposes 7 args;
   after dropping the trailing `null`, we call with 7 — but it's
   possible the wrapper now wants a different arg layout entirely.
3. **Bus mismatch** — `Gio.DBus.session` may not receive signals from
   `dbus-send` subprocess publications on some configurations; needs
   verification with `gdbus monitor`.

### Reproduction

```bash
cd /home/kutay/Documents/GitHub/time-tui
extensions/timetui-topbar/install.sh
gnome-extensions enable timetui-topbar@kutay
# Alt+F2 → r → Enter (GNOME Shell reload)
gnome-extensions info timetui-topbar@kutay  # State: ACTIVE

# Open a tab and monitor:
gdbus monitor --session --dest org.timetui.Session
# Open another tab and launch TUI:
todotui
# Start a tracker. Monitor tab should show Updated signals. If not,
# TUI is not publishing; check that ~/.config/timetui/state-path exists.
```

### Next steps to debug

1. **Run `gdbus monitor --session --dest org.timetui.Session`** in a
   separate terminal. Then start the TUI and a tracker. If no
   `Updated` signals appear → TUI is the problem (check
   `~/.config/timetui/state-path` was written, and
   `journalctl --user -b | grep dbus-send`).
2. **Run `journalctl --user -b -f | grep -i timetui`** while opening
   the popup. JS errors during render would show here.
3. **Fallback plan**: switch to file-based state export. TUI writes
   `~/.local/state/timetui/state.json` on each tick, extension reads
   via mtime polling. Removes DBus from the equation entirely. Cost:
   1 file write per tick (negligible).

### Fix candidate

If bus mismatch is the cause, simplest fix:

```javascript
// Drop the `null` sender filter — let any sender through.
this._signalSubId = Gio.DBus.session.signal_subscribe(
    IFACE,
    'Updated',
    OBJECT_PATH,
    null,
    Gio.DBusSignalFlags.NONE,
    (conn, sender, path, iface, signal, params) => { ... }
);
```

(May need to drop more or fewer args depending on the actual GJS
signature — verify with `gjs -c 'print(Gio.DBus.session.signal_subscribe
.length)'`.)

### Priority

Fix when: time-tui is used as the primary tracker and the user
specifically wants the top-bar widget. Until then, the keyboard-driven
TUI dashboard remains the primary interface; this is a "nice to have"
visibility enhancement.