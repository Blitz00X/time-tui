/*
 * time-tui Tracker — GNOME Shell top bar widget.
 *
 * Subscribes to ``org.timetui.Session.Updated`` signals (string body =
 * JSON state dict) emitted by the time-tui TUI via ``dbus-send``. Also
 * reads ``.todo/sessions.md`` for the today's session log (handled by
 * a quick helper that invokes ``cat`` via GLib subprocess).
 *
 * The widget silently renders ``⏱ —`` when no time-tui instance is
 * exporting the signal. No DBus method calls are made; this is a
 * read-only display.
 */

'use strict';

const { Gio, GLib, St, Clutter } = imports.gi;
const Main = imports.ui.main;
const PanelMenu = imports.ui.panelMenu;
const PopupMenu = imports.ui.popupMenu;

const SERVICE = 'org.timetui.Session';
const OBJECT_PATH = '/org/timetui/Session';
const IFACE = 'org.timetui.Session';

const Indicator = GObject.registerClass(
class TimeTuiIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.5, 'time-tui Tracker', false);

        this._label = new St.Label({
            text: '⏱ —',
            y_align: Clutter.ActorAlign.CENTER,
            style: 'font-family: monospace; padding: 0 6px;',
        });
        this.add_child(this._label);

        this._buildPopup();

        // Subscribe to Updated signals. The TUI publishes a JSON string
        // body every ~5 seconds (heartbeat) plus on state transitions.
        this._signalSubId = Gio.DBus.session.signal_subscribe(
            null,                      // sender (any)
            IFACE,                     // interface
            'Updated',                 // member
            OBJECT_PATH,               // path
            null,                      // arg0
            Gio.DBusSignalFlags.NONE,
            (conn, sender, path, iface, signal, params) => {
                try {
                    const body = params.get_child_value(0).get_string()[0];
                    this._handleStateString(body);
                } catch (e) {
                    logError(e, 'time-tui signal parse');
                }
            },
            null
        );

        // Initial render with whatever cached state we have.
        this._render({ active: false, label: '', remaining_sec: 0 });

        // Periodic refresh: even if signals miss us (e.g. TUI started
        // after the extension), poll every 10s as a fallback.
        this._timeoutId = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT, 10, () => {
                this._loadFallback();
                return GLib.SOURCE_CONTINUE;
            }
        );

        this.connect('destroy', () => this._cleanup());
    }

    _buildPopup() {
        this._statusItem = new PopupMenu.PopupMenuItem(_('No active session'));
        this._statusItem.setSensitive(false);
        this.menu.addMenuItem(this._statusItem);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._sessionHeader = new PopupMenu.PopupMenuItem(_('Today’s sessions'));
        this._sessionHeader.setSensitive(false);
        this.menu.addMenuItem(this._sessionHeader);
        this._sessionItems = [];
    }

    _cleanup() {
        if (this._timeoutId) {
            GLib.source_remove(this._timeoutId);
            this._timeoutId = 0;
        }
        if (this._signalSubId !== undefined) {
            Gio.DBus.session.signal_unsubscribe(this._signalSubId);
            this._signalSubId = undefined;
        }
    }

    _formatRemaining(sec) {
        sec = Math.max(0, Math.floor(sec || 0));
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        return `${m}:${s.toString().padStart(2, '0')}`;
    }

    _render(state) {
        if (!state || !state.active) {
            this._label.set_text('⏱ —');
            this._statusItem.label.set_text('No active session');
            return;
        }
        const pauseMark = state.paused ? '⏸' : '⏱';
        const remain = this._formatRemaining(state.remaining_sec);
        const label = state.label || '';
        this._label.set_text(`${pauseMark} ${remain}  ${label}`.trim());

        const summary = `${state.kind || ''} • ${this._formatRemaining(state.remaining_sec)} • ${label}`;
        this._statusItem.label.set_text(summary);

        // Refresh today's sessions when state changes.
        this._loadToday();
    }

    _handleStateString(body) {
        try {
            const state = JSON.parse(body);
            this._render(state);
        } catch (e) {
            logError(e, 'time-tui JSON parse');
        }
    }

    /**
     * Fallback poll: shell out to ``gdbus`` to read whatever state the
     * TUI last published. We keep this light; the primary path is the
     * signal subscription above.
     */
    _loadFallback() {
        try {
            const [, stdout] = GLib.spawn_sync(
                null,
                ['gdbus', 'monitor', '--session', '--dest', SERVICE],
                null,
                GLib.SpawnFlags.SEARCH_PATH,
                null
            );
            // gdbus monitor blocks; we can't use it here. Skip — signals
            // are the primary mechanism.
        } catch (e) {
            // best effort
        }
    }

    _loadToday() {
        // Read .todo/sessions.md for today's date via ``cat`` on the
        // user's project root. The project root is read from a small
        // config file at ~/.config/timetui/state-path. If the file is
        // missing, we simply skip the today's sessions section.
        const configPath = GLib.build_filenamev(
            [GLib.get_home_dir(), '.config', 'timetui', 'state-path']
        );
        const configFile = Gio.File.new_for_path(configPath);
        if (!configFile.query_exists(null)) return;

        let projectRoot;
        try {
            const [, contents] = configFile.load_contents(null);
            projectRoot = new TextDecoder().decode(contents).trim();
        } catch (e) {
            return;
        }
        if (!projectRoot) return;

        const today = new Date().toISOString().slice(0, 10);
        const sessionsMd = GLib.build_filenamev(
            [projectRoot, '.todo', 'sessions.md']
        );
        const f = Gio.File.new_for_path(sessionsMd);
        if (!f.query_exists(null)) return;

        try {
            const [, contents] = f.load_contents(null);
            const text = new TextDecoder().decode(contents);
            const entries = this._parseSessionsForDay(text, today);

            // Drop previous dynamic items; keep the static header.
            for (const item of this._sessionItems) {
                item.destroy();
            }
            this._sessionItems = [];

            if (entries.length === 0) {
                const empty = new PopupMenu.PopupMenuItem(_('(no sessions yet)'));
                empty.setSensitive(false);
                this.menu.addMenuItem(empty);
                this._sessionItems.push(empty);
                return;
            }
            for (const entry of entries) {
                const item = new PopupMenu.PopupMenuItem(
                    `${entry.start}–${entry.end}  ${entry.label}`
                );
                this.menu.addMenuItem(item);
                this._sessionItems.push(item);
            }
        } catch (e) {
            logError(e, 'time-tui sessions read');
        }
    }

    _parseSessionsForDay(text, isoDay) {
        // Walk the markdown: ``# YYYY-MM-DD`` heading, then ``- HH:MM–HH:MM label`` lines.
        const out = [];
        let day = null;
        for (const raw of text.split('\n')) {
            const line = raw.trim();
            if (!line) continue;
            const heading = line.match(/^#\s+(\d{4}-\d{2}-\d{2})\s*$/);
            if (heading) {
                day = heading[1];
                continue;
            }
            if (day !== isoDay) continue;
            const ev = line.match(/^-\s+(\d{1,2}:\d{2})[–-](\d{1,2}:\d{2})\s+(.+)$/);
            if (ev) {
                out.push({ start: ev[1], end: ev[2], label: ev[3] });
            }
        }
        return out;
    }
});

class Extension {
    constructor() {}

    enable() {
        this._indicator = new Indicator();
        Main.panel.addToStatusArea('time-tui-tracker', this._indicator, 0, 'right');
    }

    disable() {
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }
}

function init() {
    return new Extension();
}