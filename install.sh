#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP="$HOME/.local/share/wallpaper-control-centre"
mkdir -p "$APP" "$HOME/.local/bin" "$HOME/.config/autostart" "$HOME/.local/share/applications" "$HOME/Pictures/Wallpapers"

for command in cc pkg-config; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing build tool: $command. Install build-essential and pkg-config first." >&2
    exit 1
  }
done
pkg-config --exists x11 xext xrender || {
  echo "Missing X11 development libraries. Install libx11-dev libxext-dev libxrender-dev." >&2
  exit 1
}

echo "== Building the X11 desktop wallpaper helper =="
cc -O2 -Wall -Wextra "$ROOT/vendor/xwinwrap/xwinwrap.c" \
  -o "$APP/xwinwrap" -lX11 -lXext -lXrender
chmod 0755 "$APP/xwinwrap"

install -m 0644 "$ROOT/wallpaper_control_centre.py" "$APP/wallpaper_control_centre.py"
install -m 0644 "$ROOT/live_wallpaper_engine.py" "$APP/live_wallpaper_engine.py"
install -m 0644 "$ROOT/desktop_icons.py" "$APP/desktop_icons.py"
install -m 0644 "$ROOT/vendor/xwinwrap/NOVELL-LICENSE.txt" "$APP/XWINWRAP-LICENSE.txt"

cat > "$HOME/.local/bin/wallpaper-control-centre" <<'LAUNCH'
#!/usr/bin/env bash
exec /usr/bin/python3 "$HOME/.local/share/wallpaper-control-centre/wallpaper_control_centre.py" "$@"
LAUNCH
chmod 0755 "$HOME/.local/bin/wallpaper-control-centre"

cat > "$HOME/.local/share/applications/wallpaper-control-centre.desktop" <<'APPDESK'
[Desktop Entry]
Type=Application
Name=Wallpaper Control Centre
Comment=Manage static wallpapers, live videos and soundtrack
Exec=/home/prime/.local/bin/wallpaper-control-centre
Icon=preferences-desktop-wallpaper
Categories=Settings;DesktopSettings;
StartupNotify=true
Terminal=false
APPDESK

cat > "$HOME/.local/bin/wallpaper-control-centre-restore" <<'RESTORE'
#!/usr/bin/env bash
set -u
LOG="$HOME/.cache/wallpaper-control-centre-restore.log"
mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
echo "[$(date -Is)] Wallpaper restore hook started."
ready=0
for attempt in $(seq 1 45); do
  desktop_pid="$(pgrep -xo xfdesktop 2>/dev/null || true)"
  if [ -n "$desktop_pid" ] && [ -r "/proc/$desktop_pid/environ" ]; then
    while IFS= read -r -d "" entry; do
      case "$entry" in
        DISPLAY=*|DBUS_SESSION_BUS_ADDRESS=*|XDG_RUNTIME_DIR=*|XAUTHORITY=*) export "$entry" ;;
      esac
    done < "/proc/$desktop_pid/environ"
    if [ -n "${DISPLAY:-}" ] && [ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ] &&
       /usr/bin/xfconf-query -c xfce4-desktop -l 2>/dev/null | grep -Fq '/last-image'; then
      ready=1
      break
    fi
  fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "[$(date -Is)] ERROR: Could not connect to the running XFCE desktop session."
  exit 1
fi
sleep 2
/home/prime/.local/bin/wallpaper-control-centre --restore
status=$?
echo "[$(date -Is)] Restore finished with status $status."
exit "$status"
RESTORE
chmod 0755 "$HOME/.local/bin/wallpaper-control-centre-restore"

echo "Installed Wallpaper Control Centre."
echo "XWinWrap: $APP/xwinwrap"
echo "Library: $HOME/Pictures/Wallpapers"
