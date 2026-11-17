#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP="$HOME/.local/share/wallpaper-control-centre"
mkdir -p "$APP" "$HOME/.local/bin" "$HOME/.config/autostart" "$HOME/Pictures/Wallpapers"
install -m 0644 "$ROOT/wallpaper_control_centre.py" "$APP/wallpaper_control_centre.py"
install -m 0644 "$ROOT/live_wallpaper_engine.py" "$APP/live_wallpaper_engine.py"

cat > "$HOME/.local/bin/wallpaper-control-centre" <<'LAUNCH'
#!/usr/bin/env bash
exec /usr/bin/python3 "$HOME/.local/share/wallpaper-control-centre/wallpaper_control_centre.py" "$@"
LAUNCH
chmod 0755 "$HOME/.local/bin/wallpaper-control-centre"

cat > "$HOME/.local/share/applications/wallpaper-control-centre.desktop" <<'APP'
[Desktop Entry]
Type=Application
Name=Wallpaper Control Centre
Comment=Browse and manage desktop wallpapers
Exec=/home/prime/.local/bin/wallpaper-control-centre
Icon=preferences-desktop-wallpaper
Categories=Settings;DesktopSettings;
StartupNotify=true
Terminal=false
APP

cat > "$HOME/.local/bin/wallpaper-control-centre-restore" <<'RESTORE'
#!/usr/bin/env bash
set -u
LOG="$HOME/.cache/wallpaper-control-centre-restore.log"
mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
echo "[$(date -Is)] Wallpaper restore hook started."

# xfconf-query must use the same D-Bus and X11 session as xfdesktop.
# Autostart may launch this script without inheriting those variables.
ready=0
for attempt in $(seq 1 45); do
  desktop_pid="$(pgrep -xo xfdesktop 2>/dev/null || true)"
  if [ -n "$desktop_pid" ] && [ -r "/proc/$desktop_pid/environ" ]; then
    while IFS= read -r -d "" entry; do
      case "$entry" in
        DISPLAY=*|DBUS_SESSION_BUS_ADDRESS=*|XDG_RUNTIME_DIR=*|XAUTHORITY=*)
          export "$entry"
          ;;
      esac
    done < "/proc/$desktop_pid/environ"

    if [ -n "${DISPLAY:-}" ] &&
       [ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ] &&
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

# Allow xfdesktop to finish applying its initial configuration.
sleep 2
/home/prime/.local/bin/wallpaper-control-centre --restore
status=$?
echo "[$(date -Is)] Restore finished with status $status."
exit "$status"
RESTORE
chmod 0755 "$HOME/.local/bin/wallpaper-control-centre-restore"

cat > "$HOME/.config/autostart/wallpaper-control-centre-restore.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Wallpaper Control Centre Restore
Comment=Restore the saved wallpaper after XFCE desktop startup
Exec=/home/prime/.local/bin/wallpaper-control-centre-restore
OnlyShowIn=XFCE;
X-XFCE-Autostart-Phase=Desktop
StartupNotify=false
Terminal=false
Hidden=false
DESKTOP

echo "Installed. Run wallpaper-control-centre to manage your library."
echo "Library: $HOME/Pictures/Wallpapers"
