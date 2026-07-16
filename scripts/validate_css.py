#!/usr/bin/env python3
"""Validate TimeTuiApp CSS; print errors to stdout."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from textual.css._help_renderables import HelpText
from textual.css.parse import parse
from todo.ui.dashboard_screen import APP_CSS

css_path = ROOT / "todo/ui/dashboard_screen.py"
read_from = (str(css_path), "TimeTuiApp.CSS")
rules = list(parse("TimeTuiApp", APP_CSS, read_from))
errors = []
for rule in rules:
    for tok, msg in rule.errors:
        text = msg.summary if isinstance(msg, HelpText) else str(msg)
        errors.append(f"{text} @ line {tok.location[0] + 1}")

if errors:
    print("FAIL", len(errors))
    for e in errors:
        print(e)
    sys.exit(1)
print("OK", len(rules), "rules")
sys.exit(0)
