# Wallpaper Control Centre

A local-first static wallpaper manager for Debian XFCE, including Termux:X11 / PRoot desktops.

## Features

- Personal image library in ~/Pictures/Wallpapers.
- Imports PNG, JPG, JPEG, WEBP, BMP and GIF files.
- Applies wallpapers through XFCE Xfconf.
- Zoom/Fill, Scale/Fit, Stretch, Center, Tile and Span modes.
- Persists the selected image and mode in ~/.config/wallpaper-control-centre/state.json.
- Restores the saved selection during XFCE initialization.
- First-run migration adopts the image already selected in XFCE instead of replacing it with the upstream WhiteSur default.

Static-image-only: this does not install or start Fresco, Lowpaper, MPV wallpaper loops or any live-wallpaper daemon.

## Requirements

Debian XFCE, xfconf-query, Python 3, GTK 3, PyGObject (python3-gi and gir1.2-gtk-3.0).

## Install

Run as the desktop user (normally prime):

    git clone https://github.com/bhuvan0x/WALLPAPER-CONTROL-CENTRE.git
    cd WALLPAPER-CONTROL-CENTRE
    bash install.sh

Launch:

    wallpaper-control-centre

Choose Add wallpaper, select an image, choose a display mode and press Set as desktop wallpaper. Imported images are copied into the managed library.

## CLI

    wallpaper-control-centre --restore
    wallpaper-control-centre --adopt-current

--restore is used by XFCE autostart. If no state exists, it adopts the current valid XFCE wallpaper before considering the installed WhiteSur image as a last-resort fallback.

## Storage

- Library: ~/Pictures/Wallpapers/
- State: ~/.config/wallpaper-control-centre/state.json
- App: ~/.local/share/wallpaper-control-centre/
- Autostart: ~/.config/autostart/wallpaper-control-centre-restore.desktop

The application does not delete images from the library. No root access, runtime network calls, telemetry or cloud account.
