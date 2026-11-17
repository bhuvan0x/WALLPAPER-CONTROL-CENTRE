#!/usr/bin/env python3
"""XFCE live wallpaper controller using a desktop-layer X11 window.

Video is rendered by MPV inside an XWinWrap window typed as DESKTOP.
XFCE's native icon view is temporarily hidden while a transparent GTK icon
overlay is shown above the video and below normal application windows.
All XFCE icon settings are restored on stop and on recovery.
"""
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
APP = HOME / ".local/share/wallpaper-control-centre"
ENGINE = Path(__file__).resolve()
ICON_OVERLAY = APP / "desktop_icons.py"
BIN = APP / "xwinwrap"
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/runtime-{os.environ.get('USER', 'prime')}"))
RUNTIME.mkdir(parents=True, exist_ok=True)
IPC = RUNTIME / "wallpaper-control-centre-mpv.sock"
META = HOME / ".config/wallpaper-control-centre/live.json"
LOG_DIR = HOME / ".cache/wallpaper-control-centre"
LOG = LOG_DIR / "live-wallpaper.log"
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".ogv"}
MAX_VOLUME = 100
CHANNEL = "xfce4-desktop"
ICON_STYLE = "/desktop-icons/style"


class EngineError(RuntimeError):
    pass


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_meta():
    try:
        value = json.loads(META.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def xfconf(*args, check=True):
    try:
        result = subprocess.run(["xfconf-query", "-c", CHANNEL, *args],
                                text=True, capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EngineError(f"Cannot communicate with XFCE settings: {exc}") from exc
    if check and result.returncode:
        raise EngineError((result.stderr or result.stdout).strip() or "XFCE settings command failed.")
    return result


def get_icon_style():
    result = xfconf("-p", ICON_STYLE, check=False)
    if result.returncode:
        # Some clean XFCE profiles have not materialized this property yet.
        return 2
    try:
        return int(result.stdout.strip())
    except ValueError as exc:
        raise EngineError("XFCE returned an invalid desktop icon style.") from exc


def set_icon_style(value):
    xfconf("-p", ICON_STYLE, "--create", "-t", "int", "-s", str(int(value)))


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, ValueError):
        return False
    except PermissionError:
        return True


def terminate_group(pid, seconds=3):
    if not pid or int(pid) <= 1:
        return
    try:
        os.killpg(int(pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not pid_alive(pid):
            return
        time.sleep(0.1)
    try:
        os.killpg(int(pid), signal.SIGKILL)
    except ProcessLookupError:
        pass


def mpv_command(command, timeout=2.0):
    if not IPC.exists():
        raise EngineError("Live wallpaper is not running.")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout)
            client.connect(str(IPC))
            client.sendall((json.dumps({"command": command}) + "\n").encode())
            data = client.makefile("rb").readline()
            if not data:
                raise EngineError("MPV returned no response.")
            response = json.loads(data)
            if response.get("error") not in (None, "success"):
                raise EngineError(f"MPV: {response['error']}")
            return response.get("data")
    except (OSError, ValueError) as exc:
        raise EngineError(f"Could not contact MPV: {exc}") from exc


def get_property(name):
    return mpv_command(["get_property", name])


def recover_stale_state(data=None):
    data = data or read_meta()
    # If the last session died before cleanup, bring XFCE's native icons back.
    if data.get("managed_icons") and data.get("original_icon_style") is not None:
        if get_icon_style() == 0:
            set_icon_style(data["original_icon_style"])
    terminate_group(data.get("overlay_pid"))
    terminate_group(data.get("wallpaper_pid"))
    IPC.unlink(missing_ok=True)


def stop(clear_state=True):
    data = read_meta()
    try:
        if IPC.exists():
            mpv_command(["quit"])
    except EngineError:
        pass
    terminate_group(data.get("wallpaper_pid"), 3)
    terminate_group(data.get("overlay_pid"), 2)
    IPC.unlink(missing_ok=True)
    if data.get("managed_icons") and data.get("original_icon_style") is not None:
        # Do not overwrite a deliberate user change made while the wallpaper ran.
        if get_icon_style() == 0:
            set_icon_style(data["original_icon_style"])
    if clear_state:
        META.unlink(missing_ok=True)
    return True


def start(path, volume=65, audio=True, restore_on_login=False):
    path = Path(path).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in VIDEO_EXTS:
        raise EngineError("Choose a supported video: MP4, MKV, WEBM, MOV, AVI, M4V or OGV.")
    if not BIN.is_file() or not os.access(BIN, os.X_OK):
        raise EngineError("The X11 wallpaper helper is not installed. Re-run the Wallpaper Control Centre installer.")
    if not shutil_which("mpv"):
        raise EngineError("MPV is not installed.")
    if not shutil_which("xfconf-query"):
        raise EngineError("xfconf-query is not installed.")
    if not ICON_OVERLAY.is_file():
        raise EngineError("The desktop icon overlay is missing. Re-run the installer.")

    old = read_meta()
    recover_stale_state(old)
    style = get_icon_style()
    if style == 1:
        raise EngineError("XFCE is set to show minimized-application icons. Switch Desktop → Icons → Icon type to File/launcher icons or None before using live wallpapers.")
    if style not in (0, 2):
        raise EngineError(f"Unsupported XFCE desktop icon mode: {style}. No settings were changed.")

    volume = max(0, min(MAX_VOLUME, int(volume)))
    managed_icons = style == 2
    overlay = None
    wallpaper = None
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = LOG.open("ab", buffering=0)
    try:
        if managed_icons:
            # Native xfdesktop icon view and the overlay must never be shown together.
            set_icon_style(0)
            time.sleep(0.35)

        adapter = 'wid="$1"; shift; exec mpv --wid="$wid" "$@"'
        command = [
            str(BIN), "-fdt", "-ni", "-fs", "-s", "-st", "-sp", "-b", "-nf", "--",
            "/bin/sh", "-c", adapter, "wallpaper-control-centre", "WID",
            "--no-config", "--vo=x11", "--force-window=yes", "--no-border",
            "--osc=no", "--osd-level=0", "--input-default-bindings=no",
            "--input-vo-keyboard=no", "--cursor-autohide=always",
            "--audio-display=no", "--loop-file=inf",
            f"--volume={volume}", f"--mute={'no' if audio else 'yes'}",
            f"--input-ipc-server={IPC}", str(path)
        ]
        wallpaper = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                     stdout=log_handle, stderr=log_handle,
                                     start_new_session=True, close_fds=True)
        # Wait for MPV IPC to become available; fail closed if XWinWrap/MPV exits.
        deadline = time.monotonic() + 18
        while time.monotonic() < deadline:
            if wallpaper.poll() is not None:
                raise EngineError(f"XWinWrap exited early (status {wallpaper.returncode}). See {LOG}")
            if IPC.exists():
                try:
                    get_property("path")
                    break
                except EngineError:
                    pass
            time.sleep(0.2)
        else:
            raise EngineError(f"MPV did not become ready. See {LOG}")

        if managed_icons:
            overlay = subprocess.Popen([sys.executable, str(ICON_OVERLAY)],
                                       stdin=subprocess.DEVNULL, stdout=log_handle,
                                       stderr=log_handle, start_new_session=True,
                                       close_fds=True)
            time.sleep(0.8)
            if overlay.poll() is not None:
                raise EngineError(f"Desktop icon overlay exited (status {overlay.returncode}). See {LOG}")

        atomic_json(META, {
            "version": 2, "path": str(path), "volume": volume, "audio": bool(audio),
            "wallpaper_pid": wallpaper.pid, "overlay_pid": overlay.pid if overlay else None,
            "original_icon_style": style, "managed_icons": managed_icons,
            "started": int(time.time()), "restore_on_login": bool(restore_on_login),
            "backend": "xwinwrap-mpv-desktop-layer"
        })
        return wallpaper.pid
    except Exception:
        if overlay:
            terminate_group(overlay.pid)
        if wallpaper:
            terminate_group(wallpaper.pid)
        IPC.unlink(missing_ok=True)
        if managed_icons and get_icon_style() == 0:
            set_icon_style(style)
        raise
    finally:
        log_handle.close()


def shutil_which(name):
    from shutil import which
    return which(name)


def restore():
    data = read_meta()
    path = Path(data.get("path", "")).expanduser()
    if not path.is_file():
        return False
    start(path, data.get("volume", 65), data.get("audio", True))
    return True


def main():
    parser = argparse.ArgumentParser(description="XFCE live wallpaper controller")
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("start")
    p.add_argument("video")
    p.add_argument("--volume", type=int, default=65)
    p.add_argument("--no-audio", action="store_true")
    p.add_argument("--restore-on-login", action="store_true")
    sub.add_parser("stop")
    sub.add_parser("pause")
    sub.add_parser("resume")
    sub.add_parser("toggle")
    sub.add_parser("restart")
    sub.add_parser("status")
    p = sub.add_parser("volume")
    p.add_argument("value", type=int)
    p = sub.add_parser("audio")
    p.add_argument("state", choices=("on", "off", "toggle"))
    sub.add_parser("restore")
    args = parser.parse_args()
    try:
        if args.action == "start":
            pid = start(args.video, args.volume, not args.no_audio, args.restore_on_login)
            print(f"Live wallpaper started (PID {pid}).")
        elif args.action == "stop":
            stop()
            print("Live wallpaper stopped; XFCE desktop icons restored.")
        elif args.action == "restore":
            if restore():
                print("Live wallpaper restored.")
            else:
                print("No saved live wallpaper.")
        elif args.action == "pause":
            mpv_command(["set_property", "pause", True]); print("Paused.")
        elif args.action == "resume":
            mpv_command(["set_property", "pause", False]); print("Playing.")
        elif args.action == "toggle":
            paused = bool(get_property("pause"))
            mpv_command(["set_property", "pause", not paused])
            print("Paused." if not paused else "Playing.")
        elif args.action == "restart":
            mpv_command(["seek", 0, "absolute"]); mpv_command(["set_property", "pause", False]); print("Restarted.")
        elif args.action == "volume":
            value = max(0, min(MAX_VOLUME, args.value))
            mpv_command(["set_property", "volume", value])
            data = read_meta(); data["volume"] = value; atomic_json(META, data)
            print(f"Volume: {value}%")
        elif args.action == "audio":
            muted = bool(get_property("mute"))
            target = not muted if args.state == "toggle" else args.state == "off"
            mpv_command(["set_property", "mute", target])
            data = read_meta(); data["audio"] = not target; atomic_json(META, data)
            print("Audio muted." if target else "Audio enabled.")
        elif args.action == "status":
            print(json.dumps({
                "path": get_property("path"), "pause": get_property("pause"),
                "volume": get_property("volume"), "mute": get_property("mute"),
                "duration": get_property("duration"), "time_pos": get_property("time-pos")
            }, indent=2))
        return 0
    except EngineError as exc:
        print(f"Live wallpaper: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
