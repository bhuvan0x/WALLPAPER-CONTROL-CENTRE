#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP="$HOME/.local/share/wallpaper-control-centre"
mkdir -p "$APP" "$HOME/.local/bin" "$HOME/.config/autostart" "$HOME/Pictures/Wallpapers"
install -m 0644 "$ROOT/wallpaper_control_centre.py" "$APP/wallpaper_control_centre.py"
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

# Wait until XFCE desktop and its wallpaper channel are fully initialized.
ready=0
for attempt in $(seq 1 45); do
  if pgrep -u "$(id -u)" -x xfdesktop >/dev/null 2>&1 \
    && /usr/bin/xfconf-query -c xfce4-desktop -l 2>/dev/null | grep -q '/last-image
echo "Installed. Run wallpaper-control-centre to manage your library."
echo "Library: $HOME/Pictures/Wallpapers"
; then
    ready=1
    break
  fi
  sleep 1
done

if [ "$ready" -ne 1 ]; then
  echo "[$(date -Is)] ERROR: xfdesktop wallpaper settings did not become ready."
  exit 1
fi

# Let xfdesktop finish applying its initial configuration before restoring
# the user's saved selection.
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
