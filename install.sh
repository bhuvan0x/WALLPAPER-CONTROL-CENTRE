#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "\${BASH_SOURCE[0]}")" && pwd)"
APP="$HOME/.local/share/wallpaper-control-centre"
mkdir -p "$APP" "$HOME/.local/bin" "$HOME/.config/autostart" "$HOME/Pictures/Wallpapers"
install -m 0644 "$ROOT/wallpaper_control_centre.py" "$APP/wallpaper_control_centre.py"
cat > "$HOME/.local/bin/wallpaper-control-centre" <<'LAUNCH'
#!/usr/bin/env bash
exec /usr/bin/python3 "$HOME/.local/share/wallpaper-control-centre/wallpaper_control_centre.py" "$@"
LAUNCH
chmod 0755 "$HOME/.local/bin/wallpaper-control-centre"
cat > "$HOME/.config/autostart/wallpaper-control-centre-restore.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Wallpaper Control Centre Restore
Comment=Restore the saved wallpaper at XFCE login
Exec=/home/prime/.local/bin/wallpaper-control-centre --restore
OnlyShowIn=XFCE;
X-XFCE-Autostart-Phase=Initialization
StartupNotify=false
Terminal=false
Hidden=false
DESKTOP
echo "Installed. Run wallpaper-control-centre to manage your library."
echo "Library: $HOME/Pictures/Wallpapers"
