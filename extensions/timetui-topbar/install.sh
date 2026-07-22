#!/usr/bin/env bash
#
# Install timetui-topbar GNOME Shell extension.
#
# Copies files into ~/.local/share/gnome-shell/extensions/ and reports
# what to do next. Doesn't auto-enable (you'll want to verify it loads
# after a Shell restart first).
#
set -euo pipefail

UUID="timetui-topbar@kutay"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/$UUID"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing to: $DEST"
mkdir -p "$DEST"
install -m 0644 "$HERE"/metadata.json "$DEST/"
install -m 0644 "$HERE"/extension.js "$DEST/"
install -m 0644 "$HERE"/README.md "$DEST/" 2>/dev/null || true

echo
echo "Done."
echo
echo "Next steps:"
echo "  1. Restart GNOME Shell: Alt+F2, type 'r', press Enter (X11)."
echo "     On Wayland, log out and log back in."
echo "  2. Enable the extension:"
echo "       gnome-extensions enable $UUID"
echo "  3. Verify it loaded:"
echo "       gnome-extensions list --enabled | grep timetui"
echo
echo "To uninstall:"
echo "       gnome-extensions disable $UUID"
echo "       rm -rf \"$DEST\""