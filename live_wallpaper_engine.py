#!/usr/bin/env python3
"""Click-through MPV live wallpaper backend for a single-monitor XFCE desktop.

The player is embedded in xfdesktop's desktop window, then lowered beneath
its icon-view child windows. XFixes gives the video child an empty input
shape so pointer events continue to reach desktop icons.
"""
import argparse
import ctypes
import ctypes.util
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/runtime-{os.environ.get('USER', 'prime')}"))
RUNTIME.mkdir(parents=True, exist_ok=True)
IPC = RUNTIME / "wallpaper-control-centre-mpv.sock"
META = HOME / ".config/wallpaper-control-centre/live.json"
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".ogv"}
MAX_VOLUME = 100


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


def desktop_window():
    try:
        from Xlib import X, display
        from Xlib.xobject.drawable import Window
    except ImportError as exc:
        raise EngineError("python3-xlib is missing; install the Wallpaper Control Centre dependencies.") from exc

    d = display.Display()
    root = d.screen().root
    atom_type = d.intern_atom("_NET_WM_WINDOW_TYPE")
    atom_desktop = d.intern_atom("_NET_WM_WINDOW_TYPE_DESKTOP")
    atom_current = d.intern_atom("_NET_CURRENT_DESKTOP")
    atom_wm_desktop = d.intern_atom("_NET_WM_DESKTOP")
    current = root.get_full_property(atom_current, X.AnyPropertyType)
    current_desktop = int(current.value[0]) if current and len(current.value) else 0
    matches = []
    # Recurse because reparenting window managers (including xfwm4) may place
    # the client desktop window below a frame window instead of directly on root.
    pending = [(win, 0) for win in root.query_tree().children]
    while pending:
        win, depth = pending.pop()
        try:
            prop = win.get_full_property(atom_type, X.AnyPropertyType)
            if prop and atom_desktop in list(prop.value):
                geom = win.get_geometry()
                if geom.width >= 320 and geom.height >= 240:
                    desk = win.get_full_property(atom_wm_desktop, X.AnyPropertyType)
                    desk_id = int(desk.value[0]) if desk and len(desk.value) else 0xFFFFFFFF
                    if desk_id in (current_desktop, 0xFFFFFFFF):
                        matches.append((geom.width * geom.height, win.id, geom.width, geom.height))
            if depth < 5:
                pending.extend((child, depth + 1) for child in win.query_tree().children)
        except Exception:
            continue
    if not matches:
        d.close()
        raise EngineError("Could not identify the active XFCE desktop window. No window was changed.")
    matches.sort(reverse=True)
    # Termux:X11 on PrimeBook is a single-monitor desktop. Refuse ambiguous
    # equal-sized desktop windows rather than putting video on the wrong one.
    largest = matches[0]
    if len(matches) > 1 and matches[1][0] == largest[0]:
        d.close()
        raise EngineError("Multiple equal-sized XFCE desktop windows were found; refusing an ambiguous live-wallpaper target.")
    return d, root, d.create_resource_object("window", largest[1]), (largest[2], largest[3])


def set_click_through(window_id):
    lib_name = ctypes.util.find_library("Xfixes")
    x11_name = ctypes.util.find_library("X11")
    if not lib_name or not x11_name:
        raise EngineError("XFixes/X11 client libraries are missing; click-through safety cannot be guaranteed.")
    x11 = ctypes.CDLL(x11_name)
    fixes = ctypes.CDLL(lib_name)
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    fixes.XFixesQueryExtension.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    fixes.XFixesQueryExtension.restype = ctypes.c_int
    fixes.XFixesCreateRegion.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
    fixes.XFixesCreateRegion.restype = ctypes.c_ulong
    fixes.XFixesSetWindowShapeRegion.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
    fixes.XFixesDestroyRegion.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    display_name = os.environ.get("DISPLAY", "").encode() or None
    conn = x11.XOpenDisplay(display_name)
    if not conn:
        raise EngineError("Cannot open the active X11 display.")
    try:
        event_base, error_base = ctypes.c_int(), ctypes.c_int()
        if not fixes.XFixesQueryExtension(conn, ctypes.byref(event_base), ctypes.byref(error_base)):
            raise EngineError("The X server does not provide XFixes; refusing to create a window that could block desktop clicks.")
        # Create a genuinely empty XFixes region. Passing None here resets
        # the shape on some XFixes implementations and is NOT click-through.
        empty = fixes.XFixesCreateRegion(conn, None, 0)
        if not empty:
            raise EngineError("XFixes could not allocate an empty input region.")
        try:
            fixes.XFixesSetWindowShapeRegion(conn, ctypes.c_ulong(window_id), 2, 0, 0, empty)
            x11.XFlush(conn)
        finally:
            fixes.XFixesDestroyRegion(conn, empty)
    finally:
        x11.XCloseDisplay(conn)


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


def start(path, volume=65, audio=True):
    path = Path(path).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in VIDEO_EXTS:
        raise EngineError("Choose a supported video: MP4, MKV, WEBM, MOV, AVI, M4V or OGV.")
    if IPC.exists():
        try:
            get_property("path")
            mpv_command(["quit"])
            time.sleep(0.25)
        except EngineError:
            pass
        IPC.unlink(missing_ok=True)

    d, root, parent, size = desktop_window()
    before = {child.id for child in parent.query_tree().children}
    width, height = size
    cmd = [
        "mpv", "--no-config", "--vo=x11", f"--wid={parent.id}",
        "--force-window=yes", "--idle=no", "--keep-open=no",
        "--loop-file=inf", "--no-border", "--osc=no", "--osd-level=0",
        "--input-default-bindings=no", "--input-vo-keyboard=no",
        "--input-cursor=no", "--cursor-autohide=always",
        "--audio-display=no", f"--volume={max(0, min(MAX_VOLUME, int(volume)))}",
        f"--mute={'no' if audio else 'yes'}",
        f"--input-ipc-server={IPC}", str(path)
    ]
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True,
                                close_fds=True)
    except FileNotFoundError as exc:
        d.close()
        raise EngineError("MPV is not installed. Install the live-wallpaper dependencies first.") from exc

    child = None
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        try:
            d.sync()
            children = [c for c in parent.query_tree().children if c.id not in before]
            if children:
                # MPV creates its embedded video window as a child of xfdesktop.
                child = children[-1]
                break
        except Exception:
            pass
        time.sleep(0.1)

    if child is None:
        proc.terminate()
        d.close()
        IPC.unlink(missing_ok=True)
        raise EngineError("MPV did not create an embedded video window inside xfdesktop.")
    try:
        # Keep the video above the desktop's painted background but below
        # xfdesktop's icon-view child windows.
        child.configure(stack_mode=1)  # X.Below
        d.sync()
        set_click_through(child.id)
    except Exception as exc:
        try:
            mpv_command(["quit"])
        except Exception:
            proc.terminate()
        d.close()
        IPC.unlink(missing_ok=True)
        if isinstance(exc, EngineError):
            raise
        raise EngineError(f"Could not safely layer the live wallpaper: {exc}") from exc
    d.close()
    atomic_json(META, {"version": 1, "path": str(path), "volume": max(0, min(MAX_VOLUME, int(volume))),
                       "audio": bool(audio), "pid": proc.pid, "started": int(time.time())})
    return proc.pid


def stop():
    try:
        mpv_command(["quit"])
    except EngineError:
        pass
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and IPC.exists():
        time.sleep(0.1)
    IPC.unlink(missing_ok=True)
    return True


def main():
    parser = argparse.ArgumentParser(description="XFCE click-through live wallpaper engine")
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("start"); p.add_argument("video"); p.add_argument("--volume", type=int, default=65); p.add_argument("--no-audio", action="store_true")
    sub.add_parser("stop"); sub.add_parser("pause"); sub.add_parser("resume"); sub.add_parser("toggle")
    sub.add_parser("restart"); sub.add_parser("status")
    p = sub.add_parser("volume"); p.add_argument("value", type=int)
    p = sub.add_parser("audio"); p.add_argument("state", choices=("on", "off", "toggle"))
    args = parser.parse_args()
    try:
        if args.action == "start":
            pid = start(args.video, args.volume, not args.no_audio)
            print(f"Live wallpaper started (MPV PID {pid}).")
        elif args.action == "stop":
            stop(); print("Live wallpaper stopped.")
        elif args.action == "pause": mpv_command(["set_property", "pause", True]); print("Paused.")
        elif args.action == "resume": mpv_command(["set_property", "pause", False]); print("Playing.")
        elif args.action == "toggle":
            paused = bool(get_property("pause")); mpv_command(["set_property", "pause", not paused]); print("Paused." if not paused else "Playing.")
        elif args.action == "restart": mpv_command(["seek", 0, "absolute"]); mpv_command(["set_property", "pause", False]); print("Restarted.")
        elif args.action == "volume":
            value = max(0, min(MAX_VOLUME, args.value)); mpv_command(["set_property", "volume", value]); print(f"Volume: {value}%")
            meta=read_meta(); meta["volume"]=value; atomic_json(META,meta)
        elif args.action == "audio":
            muted = bool(get_property("mute"))
            target = not muted if args.state == "toggle" else args.state == "off"
            mpv_command(["set_property", "mute", target]); print("Audio enabled." if not target else "Audio muted.")
            meta=read_meta(); meta["audio"]=not target; atomic_json(META,meta)
        elif args.action == "status":
            print(json.dumps({"path": get_property("path"), "pause": get_property("pause"),
                              "volume": get_property("volume"), "mute": get_property("mute"),
                              "duration": get_property("duration"), "time_pos": get_property("time-pos")}, indent=2))
        return 0
    except EngineError as exc:
        print(f"Live wallpaper: {exc}", file=sys.stderr); return 1


if __name__ == "__main__":
    raise SystemExit(main())
