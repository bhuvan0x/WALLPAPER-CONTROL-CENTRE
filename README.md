# Wallpaper Control Centre

A local-first wallpaper manager for Debian XFCE and Termux:X11.

## Static wallpapers

- Personal library: `~/Pictures/Wallpapers`.
- Imports PNG, JPG, JPEG, WEBP, BMP and GIF.
- Applies wallpapers through XFCE Xfconf.
- Zoom/Fill, Scale/Fit, Stretch, Center, Tile and Span modes.
- Saves selection and display mode; restores on XFCE startup.
- First-run migration adopts the image already selected in XFCE.

## Live video wallpapers + soundtrack

The live backend uses a different window architecture from the first experimental implementation:

1. **XWinWrap creates an X11 wallpaper window typed as an EWMH desktop window.** MPV renders inside it; it is not embedded in xfdesktop's icon-view window.
2. **XFCE's native icon view is temporarily disabled** while live mode is active.
3. **A separate transparent GTK icon layer** displays files and launchers from the XDG Desktop folder. Its windows stay below ordinary application windows and above the desktop wallpaper.
4. The original XFCE icon-style setting is saved and restored on stop. Stale process metadata is recovered on the next start.
5. If the overlay or player fails during startup, the backend terminates what it started and restores the original icon setting.

Features:
- MP4, MKV, WEBM, MOV, AVI, M4V and OGV.
- Continuous looping; pause/resume, restart and stop.
- Soundtrack volume and mute controls apply while playback is running.
- Desktop folder changes are monitored and the icon overlay refreshes.
- Existing XFCE icon positions are read from its saved `icons.screen0-*.rc` layout where available.
- Video is configured below normal windows; overlay icons are non-focusable and kept below ordinary application windows.
- Stop restores native XFCE icons and leaves the selected static wallpaper intact.

**Known scope:** single-monitor X11. The overlay covers regular files, folders and `.desktop` launchers in the XDG Desktop directory. XFCE's special Home/Filesystem/Trash/removable-volume icons are not reimplemented by this initial overlay. Set XFCE Desktop → Icons → Icon type to **File/launcher icons** or **None** before starting; minimized-application icon mode is intentionally rejected. The app does not claim Wayland or multi-monitor support.

Fresco and Lowpaper are not used or installed.

## Requirements

Debian XFCE/X11, Python 3, GTK 3 / PyGObject, MPV, `xfconf-query`, C compiler, pkg-config, and X11 development libraries.

For the PrimeBook Termux setup, run the parent repository installer:

    bash scripts/install-wallpaper-control-centre.sh

It installs runtime and build dependencies, pulls this repository's default branch, compiles the bundled XWinWrap helper for the device architecture, and installs the app for user `prime`.

## Launch

    wallpaper-control-centre

Open **Static wallpapers** to import and apply an image. Open **Live wallpapers + music** to add a video, start it, pause/resume, restart, stop, and control its soundtrack.

The **Restore this live wallpaper at login** option is off by default. Leave it off until the actual X11 session has passed the video/icon interaction tests on the device.

## CLI

    wallpaper-control-centre --restore
    wallpaper-control-centre --adopt-current
    python3 ~/.local/share/wallpaper-control-centre/live_wallpaper_engine.py status
    python3 ~/.local/share/wallpaper-control-centre/live_wallpaper_engine.py stop

## Storage

- Library: `~/Pictures/Wallpapers/`
- Static state: `~/.config/wallpaper-control-centre/state.json`
- Live state: `~/.config/wallpaper-control-centre/live.json`
- App and compiled helper: `~/.local/share/wallpaper-control-centre/`
- Restore log: `~/.cache/wallpaper-control-centre-restore.log`
- Live backend log: `~/.cache/wallpaper-control-centre/live-wallpaper.log`

No root access at runtime, runtime network calls, telemetry or cloud account.
