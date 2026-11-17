#!/usr/bin/env python3
"""Small, clickable XDG Desktop icon layer for the live wallpaper mode."""
import os
import subprocess
import sys
from pathlib import Path

def main():
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, Gdk, Gio, GLib, GdkPixbuf
    except Exception as exc:
        print(f"Desktop icon overlay needs GTK 3 / PyGObject: {exc}", file=sys.stderr)
        return 2

    Gtk.init(sys.argv)
    desktop = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP)
    desktop = Path(desktop or (Path.home() / "Desktop")).expanduser()
    desktop.mkdir(parents=True, exist_ok=True)
    windows = []
    monitor = None
    rebuild_id = 0

    def open_item(path):
        try:
            if path.suffix.lower() == ".desktop":
                app = Gio.DesktopAppInfo.new_from_filename(str(path))
                if app:
                    app.launch([], None)
                    return
            Gio.AppInfo.launch_default_for_uri(path.as_uri(), None)
        except Exception as exc:
            print(f"Could not open {path}: {exc}", file=sys.stderr)

    def clear():
        nonlocal windows
        for win in windows:
            try:
                win.destroy()
            except Exception:
                pass
        windows = []

    def icon_for(path):
        try:
            info = Gio.File.new_for_path(str(path)).query_info(
                "standard::icon,standard::display-name", Gio.FileQueryInfoFlags.NONE, None)
            icon = info.get_icon()
            label = info.get_display_name() or path.name
        except Exception:
            icon, label = Gio.ThemedIcon.new("text-x-generic"), path.name
        if path.suffix.lower() == ".desktop":
            try:
                app = Gio.DesktopAppInfo.new_from_filename(str(path))
                if app:
                    icon = app.get_icon() or icon
                    label = app.get_display_name() or label
            except Exception:
                label = path.stem
        return icon or Gio.ThemedIcon.new("text-x-generic"), label

    def saved_positions(items, workarea):
        cfg = Path.home() / ".config/xfce4/desktop"
        candidates = []
        if cfg.is_dir():
            for file in cfg.glob("icons.screen0-*.rc"):
                import re
                match = re.fullmatch(r"icons\.screen0-(\d+)x(\d+)\.rc", file.name)
                if not match:
                    continue
                try:
                    import configparser
                    parser = configparser.ConfigParser(interpolation=None, strict=False)
                    parser.read(file, encoding="utf-8")
                    known = sum(1 for p in items if parser.has_section(str(p)))
                    w, h = map(int, match.groups())
                    score = (known, -abs(w-workarea.width)-4*abs(h-workarea.height))
                    candidates.append((score, parser))
                except Exception:
                    pass
        if not candidates:
            return {}
        parser = max(candidates, key=lambda item: item[0])[1]
        result = {}
        for path in items:
            section = str(path)
            if parser.has_section(section):
                try:
                    result[path] = (parser.getint(section, "col"), parser.getint(section, "row"))
                except Exception:
                    pass
        return result

    def rebuild():
        nonlocal windows
        clear()
        items = sorted((p for p in desktop.iterdir() if not p.name.startswith(".") and p.is_file() or p.is_dir()),
                       key=lambda p: p.name.casefold())
        display = Gdk.Display.get_default()
        mon = display.get_primary_monitor() or display.get_monitor(0)
        work = mon.get_workarea() if mon else Gdk.Rectangle()
        if work.width <= 0 or work.height <= 0:
            work = Gdk.Rectangle(0, 0, 1280, 720)
        positions = saved_positions(items, work)
        cell_w, cell_h, margin_x, margin_y = 116, 98, 12, 18
        rows = max(1, (work.height - margin_y * 2) // cell_h)

        for index, path in enumerate(items):
            icon, label_text = icon_for(path)
            win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
            win.set_title(f"Wallpaper Desktop Icon — {label_text}")
            win.set_decorated(False)
            win.set_resizable(False)
            win.set_skip_taskbar_hint(True)
            win.set_skip_pager_hint(True)
            win.set_accept_focus(False)
            win.set_focus_on_map(False)
            win.set_keep_below(True)
            win.stick()
            win.set_type_hint(Gdk.WindowTypeHint.NORMAL)
            win.set_app_paintable(True)
            win.set_size_request(112, 94)
            visual = win.get_screen().get_rgba_visual()
            if visual:
                win.set_visual(visual)

            event = Gtk.EventBox()
            event.set_visible_window(False)
            event.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
            win.add(event)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.START)
            box.set_border_width(4)
            event.add(box)

            image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.DIALOG)
            image.set_pixel_size(48)
            image.set_halign(Gtk.Align.CENTER)
            box.pack_start(image, False, False, 0)
            label = Gtk.Label(label=label_text)
            label.set_justify(Gtk.Justification.CENTER)
            label.set_line_wrap(True)
            label.set_line_wrap_mode(2)
            label.set_max_width_chars(14)
            label.set_lines(2)
            label.set_ellipsize(3)
            label.set_size_request(104, -1)
            label.set_halign(Gtk.Align.CENTER)
            box.pack_start(label, False, False, 0)
            event.set_tooltip_text(str(path))

            def clicked(widget, ev, target=path):
                if ev.type == Gdk.EventType._2BUTTON_PRESS and ev.button == 1:
                    open_item(target)
                    return True
                return False
            event.connect("button-press-event", clicked)

            if path in positions:
                col, row = positions[path]
            else:
                col, row = index // rows, index % rows
            win.move(work.x + margin_x + col * cell_w, work.y + margin_y + row * cell_h)
            win.show_all()
            win.set_keep_below(True)
            windows.append(win)
        return False

    css = Gtk.CssProvider()
    css.load_from_data(b"""
      window { background-color: transparent; }
      label { color: #ffffff; font-weight: 500;
              text-shadow: 0 1px 3px rgba(0,0,0,0.98);
              background-color: rgba(0,0,0,0.22);
              border-radius: 4px; padding: 1px 3px; }
    """)
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    rebuild()

    def changed(*_):
        nonlocal rebuild_id
        if rebuild_id:
            GLib.source_remove(rebuild_id)
        rebuild_id = GLib.timeout_add(350, rebuild)
    try:
        monitor = Gio.File.new_for_path(str(desktop)).monitor_directory(Gio.FileMonitorFlags.NONE, None)
        monitor.connect("changed", changed)
    except Exception as exc:
        print(f"Desktop folder monitor unavailable: {exc}", file=sys.stderr)
    try:
        Gtk.main()
    finally:
        clear()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
