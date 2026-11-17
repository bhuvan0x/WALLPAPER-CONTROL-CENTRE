# Wallpaper Control Centre

A local-first wallpaper manager for Debian XFCE, including Termux:X11 / PRoot desktops.

## Static wallpapers

- Personal library in `~/Pictures/Wallpapers`.
- Imports PNG, JPG, JPEG, WEBP, BMP and GIF files.
- Applies images through XFCE Xfconf.
- Zoom/Fill, Scale/Fit, Stretch, Center, Tile and Span modes.
- Persists the selected image and display mode.
- Restores the saved static wallpaper during XFCE startup.
- First-run migration adopts the image already selected in XFCE.

## Live video wallpapers + soundtrack

- Imports MP4, MKV, WEBM, MOV, AVI, M4V and OGV files into the same library.
- MPV playback with continuous looping.
- Play/pause, resume, restart and stop controls.
- Live volume slider and audio enable/disable.
- Saves the selected video, volume and audio preference; restores it after XFCE startup.
- Uses an embedded X11 child window attached to the XFCE desktop window, not a freestanding always-on-top player.
- Lowers the video child beneath XFCE desktop children and applies an empty XFixes input shape so desktop icon clicks pass through.

**Safety behavior:** if the active XFCE desktop window cannot be identified unambiguously, or XFixes cannot establish click-through input, the engine refuses to start rather than creating a window that can cover or intercept the desktop. The first implementation targets the single-monitor PrimeBook setup. It does not claim multi-monitor support.

The live backend is new and must be validated on the actual Termux:X11 session before being enabled as a daily startup feature. Static wallpaper selection and restore remain available independently. Fresco and Lowpaper are not used or installed.

## Requirements

Debian XFCE, Python 3, GTK 3 / PyGObject, `xfconf-query`, MPV, `python3-xlib`, and the XFixes runtime library (`libxfixes3`).

For the PrimeBook Termux setup, run the parent repository installer:

    bash scripts/install-wallpaper-control-centre.sh

It installs the Debian packages, pulls this repository's default branch and installs the application for user `prime`.

## Install manually

    git clone https://github.com/bhuvan0x/WALLPAPER-CONTROL-CENTRE.git
    cd WALLPAPER-CONTROL-CENTRE
    bash install.sh

Launch:

    wallpaper-control-centre

Open the **Static wallpapers** tab to import and apply an image. Open **Live wallpapers + music** to import a video, start it, pause/resume, restart, stop, change volume or mute its soundtrack.

## CLI

    wallpaper-control-centre --restore
    wallpaper-control-centre --adopt-current
    python3 ~/.local/share/wallpaper-control-centre/live_wallpaper_engine.py status
    python3 ~/.local/share/wallpaper-control-centre/live_wallpaper_engine.py stop

The XFCE restore hook restores the static image first, then attempts the previously selected live video. If live playback cannot start, it logs a warning and leaves the static wallpaper intact.

## Storage

- Library: `~/Pictures/Wallpapers/`
- Static state: `~/.config/wallpaper-control-centre/state.json`
- Live state: `~/.config/wallpaper-control-centre/live.json`
- App: `~/.local/share/wallpaper-control-centre/`
- Autostart: `~/.config/autostart/wallpaper-control-centre-restore.desktop`
- Restore log: `~/.cache/wallpaper-control-centre-restore.log`

The application does not delete library media. No root access at runtime, runtime network calls, telemetry or cloud account.
