"""
Pomodoro timer screen.
Keys: space start/pause   r reset   b/q back
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.color import Color
from textual.containers import Vertical
from textual.renderables.blank import Blank
from textual.screen import Screen
from textual.widgets import Static

_WORK_S        = 25 * 60
_SHORT_BREAK_S =  5 * 60
_LONG_BREAK_S  = 15 * 60


class PomodoroScreen(Screen):
    BINDINGS = [
        Binding("space", "toggle_timer", "Start/Pause", show=True),
        Binding("r",     "reset_timer",  "Reset",       show=True),
        Binding("b",     "go_back",      "Back",        show=True),
        Binding("q",     "go_back",      "Back",        show=False),
    ]

    DEFAULT_CSS = """
    PomodoroScreen {
        align: center middle;
        background: $background;
    }
    #pomo-box {
        width: 52;
        height: auto;
        border: solid $primary-darken-2;
        background: $surface-darken-1;
        padding: 1 3;
        layout: vertical;
    }
    #pomo-phase    { text-align: center; margin-bottom: 1; }
    #pomo-task     { text-align: center; color: $warning; margin-bottom: 1; }
    #pomo-clock    { text-align: center; text-style: bold; }
    #pomo-bar      { text-align: center; margin-bottom: 1; }
    #pomo-sessions { text-align: center; color: $text-muted; }
    #pomo-status   { text-align: center; color: $text-muted; }
    #pomo-keys     {
        text-align: center;
        color: $text-muted;
        text-style: dim;
        border-top: solid $primary-darken-3;
        margin-top: 1;
        padding-top: 1;
    }
    """

    # Fix: return Blank so Textual can render this screen as background when
    # another screen is pushed on top.
    def render(self) -> Blank:
        return Blank(self.styles.background)

    def __init__(self, task_name: str = "") -> None:
        super().__init__()
        self._task_name = task_name
        self._phase     = "work"
        self._sessions  = 0
        self._remaining = _WORK_S
        self._total     = _WORK_S
        self._running   = False

    def compose(self) -> ComposeResult:
        with Vertical(id="pomo-box"):
            yield Static("", id="pomo-phase")
            yield Static("", id="pomo-task")
            yield Static("", id="pomo-clock")
            yield Static("", id="pomo-bar")
            yield Static("", id="pomo-sessions")
            yield Static("", id="pomo-status")
            yield Static(
                "[dim]space[/] start/pause   [dim]r[/] reset   [dim]b[/] back",
                id="pomo-keys",
            )

    def on_mount(self) -> None:
        self._draw()

    def _draw(self) -> None:
        colors = {"work": "red", "short_break": "green", "long_break": "cyan"}
        labels = {
            "work":        "── FOCUS ──",
            "short_break": "── SHORT BREAK ──",
            "long_break":  "── LONG BREAK ──",
        }
        c    = colors[self._phase]
        mins, secs = divmod(self._remaining, 60)
        bw   = 30
        done = max(0, min(bw, int((1 - self._remaining / self._total) * bw)))
        bar  = "█" * done + "░" * (bw - done)
        pct  = int((1 - self._remaining / self._total) * 100)
        dots = "  ".join("●" if i < self._sessions % 4 else "○" for i in range(4))
        st   = "▶ running" if self._running else "⏸ paused"

        self.query_one("#pomo-phase",    Static).update(f"[bold {c}]{labels[self._phase]}[/]")
        self.query_one("#pomo-task",     Static).update(
            f"[dim]task:[/] {self._task_name}" if self._task_name else ""
        )
        self.query_one("#pomo-clock",    Static).update(f"[bold {c}]{mins:02d}:{secs:02d}[/]")
        self.query_one("#pomo-bar",      Static).update(f"[{c}]{bar}[/] [dim]{pct}%[/]")
        self.query_one("#pomo-sessions", Static).update(f"{dots}  [dim]{self._sessions} done[/]")
        self.query_one("#pomo-status",   Static).update(f"[dim]{st}[/]")

    def _tick(self) -> None:
        if not self._running: return
        self._remaining -= 1
        self._draw()
        if self._remaining <= 0:
            self._phase_complete()
        else:
            self.set_timer(1.0, self._tick)

    def _phase_complete(self) -> None:
        self._running = False
        if self._phase == "work":
            self._sessions += 1
            if self._sessions % 4 == 0:
                self._phase, self._total, self._remaining = "long_break",  _LONG_BREAK_S, _LONG_BREAK_S
                self.notify("Long break — 15 min ☕", title="Pomodoro")
            else:
                self._phase, self._total, self._remaining = "short_break", _SHORT_BREAK_S, _SHORT_BREAK_S
                self.notify("Short break — 5 min 🌿", title="Pomodoro")
        else:
            self._phase, self._total, self._remaining = "work", _WORK_S, _WORK_S
            self.notify("Back to work 💪", title="Pomodoro")
        self._draw()

    def action_toggle_timer(self) -> None:
        self._running = not self._running
        if self._running:
            self.set_timer(1.0, self._tick)
        self._draw()

    def action_reset_timer(self) -> None:
        self._running   = False
        self._phase     = "work"
        self._remaining = _WORK_S
        self._total     = _WORK_S
        self._draw()

    def action_go_back(self) -> None:
        self._running = False
        self.app.pop_screen()
