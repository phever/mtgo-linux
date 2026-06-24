#!/usr/bin/env python3
"""Apply MTGO-on-Wine performance flags to the deployed MTGO.exe.config.

Diagnosed 2026-06-24: collection search/scroll froze MTGO with one WPF UI thread
pinned at ~100% CPU in userspace for 30s-2min. Cause = WPF-under-Wine UI-thread
pathologies. These four appSettings (shipped by MTGO, default false) disable them:
  DisableAutomationPeer / PurgeAutomationEvents  -> stop the UI Automation peer storm
  DisableStylusInput / DisableTabletDevices      -> stop the WPF stylus/touch thread

Idempotent. Finds the current ClickOnce deploy dir, so it survives MTGO updates.
Run standalone, or it is invoked automatically by mtgo-launch.sh.
"""
import re, sys, glob, pathlib, shutil

PFX = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                   else "/home/mike/Games/magic-the-gathering-online")
FLAGS = ["DisableAutomationPeer", "PurgeAutomationEvents",
         "DisableStylusInput", "DisableTabletDevices"]

cfgs = glob.glob(str(PFX / "drive_c/users/*/AppData/Local/Apps/2.0/**/MTGO.exe.config"),
                 recursive=True)
if not cfgs:
    print("MTGO.exe.config not found — is MTGO installed?", file=sys.stderr); sys.exit(1)

changed_any = False
for cfg in cfgs:
    p = pathlib.Path(cfg)
    text = p.read_text(encoding="utf-8-sig")
    orig = text
    for key in FLAGS:
        text = re.sub(rf'(<add key="{key}" value=")false("\s*/>)', r'\1true\2', text)
    if text != orig:
        if not pathlib.Path(str(p) + ".orig").exists():
            shutil.copy2(p, str(p) + ".orig")
        p.write_text(text, encoding="utf-8")
        changed_any = True
        print(f"tuned: {p}")
    else:
        # report current state
        state = {k: (re.search(rf'<add key="{k}" value="(\w+)"', text) or [None,"?"])[1]
                 if False else re.search(rf'<add key="{k}" value="(\w+)"', text) for k in FLAGS}
        print(f"already set (no change): {p}")
for key in FLAGS:
    m = re.search(rf'<add key="{key}" value="(\w+)"', pathlib.Path(cfgs[0]).read_text(encoding="utf-8-sig"))
    print(f"  {key} = {m.group(1) if m else '?'}")
sys.exit(0)
