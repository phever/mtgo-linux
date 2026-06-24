#!/usr/bin/env bash
# Launch the already-installed MTGO (no Lutris needed).
# Uses GE-Proton11-1 via Lutris's bundled umu-launcher, with sound disabled.
# The prefix at WINEPREFIX was built and verified on 2026-06-24.
set -euo pipefail

export GAMEID="umu-mtgo"
export STORE="none"
export PROTONPATH="${PROTONPATH:-$HOME/.local/share/Steam/compatibilitytools.d/GE-Proton11-1}"
export WINEPREFIX="${WINEPREFIX:-/home/mike/Games/magic-the-gathering-online}"
export PROTON_VERB="waitforexitandrun"

# Disable GE-Proton11's brand-new in-kernel ntsync. Diagnosed 2026-06-24: with
# ntsync, scrolling/searching the collection spawned a swarm of image-load threads
# that convoyed on locks with delayed wakeups -> 30s-2min freezes. Falling back to
# fsync (futex) wakes them promptly and the freezes disappear.
export PROTON_NO_NTSYNC=1

UMU="$HOME/.local/share/lutris/runtime/umu/umu-run"

# Re-apply the WPF-under-Wine performance flags before each launch. MTGO updates
# replace MTGO.exe.config (in a new ClickOnce deploy dir), so this keeps the fix
# for the collection-scroll/search freeze (CPU-bound WPF UI thread) sticking.
python3 "$(dirname "$0")/mtgo-tune.py" "$WINEPREFIX" || true

# Launch via setup.exe (the ClickOnce activator), NOT the deployed MTGO.exe.
exec "$UMU" "$WINEPREFIX/setup.exe" "$@"
