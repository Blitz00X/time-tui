"""Ensure dashboard APP_CSS parses under Textual (no invalid properties)."""
from __future__ import annotations

from pathlib import Path

from textual.css._help_renderables import HelpText
from textual.css.parse import parse

from todo.ui.dashboard_screen import APP_CSS


def test_app_css_parses_without_errors():
    css_path = Path(__file__).resolve().parents[1] / "ui/dashboard_screen.py"
    rules = list(parse("TimeTuiApp", APP_CSS, (str(css_path), "TimeTuiApp.CSS")))
    errors: list[str] = []
    for rule in rules:
        for tok, msg in rule.errors:
            text = msg.summary if isinstance(msg, HelpText) else str(msg)
            errors.append(f"{text} @ line {tok.location[0] + 1}")
    assert not errors, "CSS errors:\n" + "\n".join(errors)
