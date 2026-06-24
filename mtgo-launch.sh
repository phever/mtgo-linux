#!/usr/bin/env bash
# Launch the installed MTGO under GE-Proton with the Linux freeze fixes applied.
#
# Self-contained and portable: auto-detects umu-run + the newest GE-Proton, finds
# the Wine prefix, re-applies MTGO's WPF performance flags on every launch (MTGO
# updates a lot and each update reverts MTGO.exe.config), and disables ntsync.
#
#   ./mtgo-launch.sh              launch MTGO
#   ./mtgo-launch.sh --tune-only  only re-apply the config flags, then exit
#                                 (used as the Lutris prelaunch step)
#   WINEPREFIX=/path ./mtgo-launch.sh   override the install location
set -euo pipefail

# --- locate the Wine prefix: this script's dir if it lives in the prefix, else default
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$SELF_DIR/drive_c" ]; then
  export WINEPREFIX="${WINEPREFIX:-$SELF_DIR}"
else
  export WINEPREFIX="${WINEPREFIX:-$HOME/Games/magic-the-gathering-online}"
fi

# --- FIX 1: re-apply MTGO's WPF-under-Wine performance flags. Without these, scrolling
# a big collection result set pins the WPF UI thread at ~100% CPU (UI Automation peer
# storm + the stylus/touch input thread) and freezes for 30s-2min.
find "$WINEPREFIX" -path '*Apps/2.0*' -name MTGO.exe.config -exec sed -i -E \
  's/("(DisableAutomationPeer|PurgeAutomationEvents|DisableStylusInput|DisableTabletDevices)" value=")false/\1true/g' \
  {} + 2>/dev/null || true
if [ "${1:-}" = "--tune-only" ]; then
  echo "MTGO WPF flags applied in $WINEPREFIX"; exit 0
fi

# --- locate umu-run (native Lutris, Flatpak Lutris, or a system install)
UMU=""
for c in "$HOME/.local/share/lutris/runtime/umu/umu-run" \
         "$HOME/.var/app/net.lutris.Lutris/data/lutris/runtime/umu/umu-run" \
         "$(command -v umu-run 2>/dev/null || true)"; do
  if [ -n "$c" ] && [ -x "$c" ]; then UMU="$c"; break; fi
done
if [ -z "$UMU" ]; then echo "umu-run not found (install Lutris or umu-launcher)" >&2; exit 1; fi

# --- newest installed GE-Proton; else let umu fetch the latest
PROTONPATH="${PROTONPATH:-$(ls -d "$HOME"/.local/share/Steam/compatibilitytools.d/GE-Proton* \
  "$HOME"/.steam/root/compatibilitytools.d/GE-Proton* 2>/dev/null | sort -V | tail -1 || true)}"
[ -z "$PROTONPATH" ] && PROTONPATH="GE-Proton"
export PROTONPATH

export GAMEID="umu-mtgo" STORE="none" PROTON_VERB="waitforexitandrun"

# --- FIX 2: disable GE-Proton11's brand-new in-kernel ntsync. With it, scrolling the
# collection convoyed MTGO's image-load threads on locks with delayed wakeups -> long
# freezes. Falling back to fsync wakes them promptly.
export PROTON_NO_NTSYNC=1

# Launch via setup.exe (the ClickOnce activator), NOT the deployed MTGO.exe.
exec "$UMU" "$WINEPREFIX/setup.exe" "$@"
