# MTGO on Linux via GE-Proton — working setup

Verified working **2026-06-24** on Arch Linux (Wine/GE-Proton11-1, Lutris 0.5.22).
Reaches the MTGO login screen; passes EULA validation (the historical crash point).

## What's here

| File | Purpose |
|------|---------|
| `magic-the-gathering-online.yml` | Lutris install script (GE-Proton, modernized). Import into Lutris to reproduce the whole install from scratch. |
| `mtgo-launch.sh` | Launch the already-installed client directly (no Lutris needed). Applies all fixes. |
| `mtgo-tune.py` | Re-applies the WPF performance flags to MTGO's config (run by the launcher; survives updates). |
| `mtgo-diag.py` | The freeze diagnostic sampler (per-thread CPU/syscall/wait). Keep for future debugging. |

(The `diag/` dir holds the local capture logs from the investigation; it's gitignored since the
captures include LAN IPs. Run `mtgo-diag.py` to regenerate it.)

## The install (already done)

Installed at **`/home/mike/Games/magic-the-gathering-online/`** using:

- **Runner:** GE-Proton11-1 (latest, released 2026-06-24) via Lutris's bundled `umu-run`.
- **Deps (winetricks):** `corefonts`, `dotnet48` (.NET Framework 4.8 — MTGO is .NET Framework, *not* .NET Core).
- **`sound=disabled`** ← the key fix. MTGO crashes under Wine the instant a sound plays
  (EULA validation / match start — WineHQ bug 48852). Disabling Wine audio makes it run.
- **Launched via `setup.exe`**, the ClickOnce bootstrapper — **not** the deployed `MTGO.exe`.
  Running `MTGO.exe` directly errors with *"This is a networked application"*.

## The freeze fix (collection scroll/search froze for 30s–2min)

Diagnosed 2026-06-24 with `mtgo-diag.py`. Two independent causes, both now fixed:

1. **WPF UI thread pinned at ~100% CPU** when a large result set populated. Cause: under
   Wine, WPF builds a UI-Automation peer for every grid item and runs the stylus/touch
   input thread. Fix — four MTGO appSettings flipped to `true` (applied by `mtgo-tune.py`,
   re-run on every launch so MTGO updates can't undo it):
   `DisableAutomationPeer`, `PurgeAutomationEvents`, `DisableStylusInput`, `DisableTabletDevices`.
2. **Lock convoy / delayed wakeups** — after #1, scrolling spawned a swarm of image-load
   threads (hundreds of HTTP connections) that piled up on locks and only released on a
   timeout. Cause: **GE-Proton11-1's brand-new in-kernel `ntsync`** (released the same day).
   Fix — **`PROTON_NO_NTSYNC=1`**, falling back to `fsync`, which wakes the threads promptly.

Evidence: with `ntsync` on, one thread sat at 99% userspace (or 88 threads blocked on
locks) for the whole freeze; with it off, the same scroll shows only brief 1–2s busy
spikes and recovers instantly.

## Launch it

```bash
./mtgo-launch.sh        # sets PROTON_NO_NTSYNC=1, applies WPF flags, then launches
```

Then enter your MTGO account credentials at the login screen.

## In Lutris

Registered in the **native** Lutris (`/usr/bin/lutris`, id 6) — appears as
"Magic The Gathering Online", launches via GE-Proton + `setup.exe`.

You also have a **Flatpak** Lutris (`net.lutris.Lutris`), which was running during setup,
so the entry was **not** added there (editing a live DB is unsafe). To add it to the
Flatpak Lutris: import `magic-the-gathering-online.yml` via **+ → Install from a local
file** (it installs to the same `~/Games/magic-the-gathering-online` path).

## Notes / troubleshooting

- **Updates:** MTGO patches itself via ClickOnce on launch through `setup.exe`. No action needed.
- **Sound:** intentionally off. Re-enabling it (`winetricks sound=pulse`) risks the startup crash.
- **Re-running the installer** is safe; it re-uses the existing deployment.
- DB backup before registration: `~/.local/share/lutris/pga.db.bak-*`.
