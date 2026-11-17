#!/usr/bin/env python3
"""Static and live wallpaper manager for XFCE / Termux:X11."""
import argparse, json, os, shutil, subprocess, sys, uuid
from pathlib import Path

HOME=Path.home(); LIBRARY=HOME/"Pictures"/"Wallpapers"
CONFIG=HOME/".config"/"wallpaper-control-centre"/"state.json"
LIVE_CONFIG=HOME/".config"/"wallpaper-control-centre"/"live.json"
APP=HOME/".local/share/wallpaper-control-centre"
ENGINE=APP/"live_wallpaper_engine.py"
IMAGE_EXTS={".png",".jpg",".jpeg",".webp",".bmp",".gif"}
VIDEO_EXTS={".mp4",".mkv",".webm",".mov",".avi",".m4v",".ogv"}
MODES={"none":0,"centered":1,"tiled":2,"stretched":3,"scaled":4,"zoomed":5,"spanned":6}
CHANNEL="xfce4-desktop"
class WallpaperError(RuntimeError): pass

def query(*args,check=True):
    try: p=subprocess.run(["xfconf-query","-c",CHANNEL,*args],text=True,capture_output=True)
    except FileNotFoundError as e: raise WallpaperError("xfconf-query is unavailable.") from e
    if check and p.returncode: raise WallpaperError((p.stderr or p.stdout).strip() or "XFCE rejected the setting.")
    return p

def properties():
    p=query("-l",check=False); found=[x.strip() for x in p.stdout.splitlines() if x.strip().endswith("/last-image")]
    return found or ["/backdrop/screen0/monitor0/workspace0/last-image"]

def current():
    for prop in properties():
        p=query("-p",prop,check=False); value=p.stdout.strip()
        if p.returncode==0 and value and Path(value).is_file(): return Path(value).expanduser().resolve()
    return None

def read_json(path):
    try:
        obj=json.loads(path.read_text(encoding="utf-8")); return obj if isinstance(obj,dict) else {}
    except (OSError,ValueError): return {}

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8"); os.replace(tmp,path)

def state(): return read_json(CONFIG)

def apply(path,mode="zoomed",persist=True):
    path=path.expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS: raise WallpaperError(f"Unsupported or missing image: {path}")
    if mode not in MODES: mode="zoomed"
    for prop in properties():
        query("-p",prop,"--create","-t","string","-s",str(path))
        query("-p",prop[:-len("last-image")]+"image-style","--create","-t","int","-s",str(MODES[mode]))
    if persist: save(CONFIG,{"version":1,"image":str(path),"mode":mode})

def engine(*args,check=True):
    if not ENGINE.is_file(): raise WallpaperError("Live wallpaper engine is not installed.")
    try: p=subprocess.run([sys.executable,str(ENGINE),*map(str,args)],text=True,capture_output=True,timeout=45)
    except (OSError,subprocess.TimeoutExpired) as e: raise WallpaperError(f"Live wallpaper command failed: {e}") from e
    output=(p.stdout or "").strip()
    if check and p.returncode: raise WallpaperError((p.stderr or output or "Live wallpaper command failed.").strip())
    return output

def restore_live():
    data=read_json(LIVE_CONFIG); path=Path(data.get("path","")).expanduser()
    if not data.get("restore_on_login",False) or not path.is_file(): return
    try:
        engine("start",path,"--volume",int(data.get("volume",65)),*([] if data.get("audio",True) else ["--no-audio"]))
        print(f"Restored live wallpaper: {path}")
    except WallpaperError as exc:
        print(f"Live wallpaper restore skipped: {exc}",file=sys.stderr)

def restore():
    data=state(); saved=Path(data["image"]).expanduser() if data.get("image") else None; mode=data.get("mode","zoomed")
    if saved and saved.is_file(): apply(saved,mode,False); print(f"Restored wallpaper: {saved}")
    else:
        selected=current()
        if selected: apply(selected,mode,True); print(f"Adopted current XFCE wallpaper: {selected}")
        else:
            fallback=HOME/".local/share/backgrounds/WhiteSur-wallpaper.png"
            if fallback.is_file(): apply(fallback,"zoomed",True); print(f"Initialized with WhiteSur fallback: {fallback}")
            else: raise WallpaperError("No saved wallpaper or valid XFCE wallpaper. Open the manager and add an image.")
    restore_live()

def import_media(source,extensions):
    source=source.expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in extensions: raise WallpaperError("Unsupported or missing media file.")
    LIBRARY.mkdir(parents=True,exist_ok=True)
    if source.parent==LIBRARY.resolve(): return source
    target=LIBRARY/source.name
    if target.exists(): target=LIBRARY/f"{source.stem}-{uuid.uuid4().hex[:8]}{source.suffix.lower()}"
    shutil.copy2(source,target); return target

def gui():
    try:
        import gi
        gi.require_version("Gtk","3.0")
        from gi.repository import Gtk,GdkPixbuf
    except Exception as e: print(f"GTK 3 / PyGObject unavailable: {e}",file=sys.stderr); return 2

    class Main(Gtk.Window):
        def __init__(self):
            super().__init__(title="Wallpaper Control Centre"); self.set_default_size(1020,650); self.set_border_width(18)
            self.selected_image=None; self.selected_video=None
            root=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12); self.add(root)
            title=Gtk.Label(); title.set_markup("<span size='xx-large' weight='bold'>Wallpaper Control Centre</span>"); title.set_xalign(0); root.pack_start(title,False,False,0)
            note=Gtk.Label(label="Your desktop, your atmosphere — static images, live video and soundtrack."); note.set_xalign(0); root.pack_start(note,False,False,0)
            self.tabs=Gtk.Notebook(); root.pack_start(self.tabs,True,True,0)
            self.image_store=Gtk.ListStore(GdkPixbuf.Pixbuf,str,str)
            self.image_view=Gtk.IconView.new(); self.image_view.set_model(self.image_store); self.image_view.set_pixbuf_column(0); self.image_view.set_text_column(1); self.image_view.set_item_width(160); self.image_view.set_spacing(12); self.image_view.connect("selection-changed",self.select_image)
            image_page=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=16); image_scroll=Gtk.ScrolledWindow(); image_scroll.add(self.image_view); image_page.pack_start(image_scroll,True,True,0)
            image_side=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10); image_side.set_size_request(230,-1); image_page.pack_start(image_side,False,False,0)
            self.preview=Gtk.Image(); self.preview.set_size_request(210,140); image_side.pack_start(self.preview,False,False,0)
            self.image_info=Gtk.Label(label="Select an image"); self.image_info.set_line_wrap(True); self.image_info.set_xalign(0); image_side.pack_start(self.image_info,False,False,0)
            image_side.pack_start(Gtk.Label(label="Display mode",xalign=0),False,False,0); self.mode=Gtk.ComboBoxText()
            for key,label in [("zoomed","Zoom / Fill"),("scaled","Scale / Fit"),("stretched","Stretch"),("centered","Center"),("tiled","Tile"),("spanned","Span")]: self.mode.append(key,label)
            self.mode.set_active_id(state().get("mode","zoomed")); image_side.pack_start(self.mode,False,False,0)
            self.add_button(image_side,"＋  Add image",self.add_image)
            self.add_button(image_side,"Set as desktop wallpaper",self.apply_selected)
            self.add_button(image_side,"Refresh library",lambda *_:self.refresh())
            self.tabs.append_page(image_page,Gtk.Label(label="Static wallpapers"))

            live_page=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=16)
            self.video_store=Gtk.ListStore(str,str); self.video_view=Gtk.TreeView(model=self.video_store); self.video_view.set_headers_visible(False)
            renderer=Gtk.CellRendererText(); column=Gtk.TreeViewColumn("Live wallpapers",renderer,text=0); self.video_view.append_column(column); self.video_view.get_selection().connect("changed",self.select_video)
            video_scroll=Gtk.ScrolledWindow(); video_scroll.add(self.video_view); live_page.pack_start(video_scroll,True,True,0)
            live_side=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10); live_side.set_size_request(270,-1); live_page.pack_start(live_side,False,False,0)
            self.video_info=Gtk.Label(label="Select a video wallpaper"); self.video_info.set_line_wrap(True); self.video_info.set_xalign(0); live_side.pack_start(self.video_info,False,False,0)
            self.add_button(live_side,"＋  Add video",self.add_video)
            self.add_button(live_side,"Start / apply live wallpaper",self.start_video)
            self.add_button(live_side,"Pause / resume",self.toggle_pause)
            self.add_button(live_side,"Restart video",self.restart_video)
            self.add_button(live_side,"Stop live wallpaper",self.stop_video)
            live_side.pack_start(Gtk.Label(label="Wallpaper music volume",xalign=0),False,False,0)
            saved=read_json(LIVE_CONFIG); self.volume=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,0,100,1); self.volume.set_value(int(saved.get("volume",65))); self.volume.set_digits(0); live_side.pack_start(self.volume,False,False,0)
            self.volume.connect("value-changed",self.volume_changed)
            self.audio=Gtk.CheckButton(label="Enable wallpaper audio"); self.audio.set_active(bool(saved.get("audio",True))); live_side.pack_start(self.audio,False,False,0)
            self.audio.connect("toggled",self.audio_changed)
            self.restore_live=Gtk.CheckButton(label="Restore this live wallpaper at login")
            self.restore_live.set_active(bool(saved.get("restore_on_login",False)))
            live_side.pack_start(self.restore_live,False,False,0)
            hint=Gtk.Label(label="Video loops continuously. Desktop icons and clicks remain above the video layer."); hint.set_line_wrap(True); hint.set_xalign(0); live_side.pack_start(hint,False,False,0)
            self.tabs.append_page(live_page,Gtk.Label(label="Live wallpapers + music"))
            self.status=Gtk.Label(label=str(LIBRARY)); self.status.set_xalign(0); self.status.set_line_wrap(True); root.pack_end(self.status,False,False,0)
            self.refresh(); self.connect("destroy",Gtk.main_quit)

        def add_button(self,parent,label,callback):
            button=Gtk.Button(label=label); button.connect("clicked",callback); parent.pack_start(button,False,False,0)

        def alert(self,message,kind=Gtk.MessageType.ERROR):
            d=Gtk.MessageDialog(transient_for=self,flags=Gtk.DialogFlags.MODAL,message_type=kind,buttons=Gtk.ButtonsType.CLOSE,text=message); d.run(); d.destroy()

        def choose_file(self,title,patterns):
            d=Gtk.FileChooserDialog(title=title,parent=self,action=Gtk.FileChooserAction.OPEN); d.add_buttons("Cancel",Gtk.ResponseType.CANCEL,"Add",Gtk.ResponseType.ACCEPT)
            f=Gtk.FileFilter(); f.set_name("Supported media")
            for pattern in patterns: f.add_pattern(pattern)
            d.add_filter(f); result=Path(d.get_filename()) if d.run()==Gtk.ResponseType.ACCEPT else None; d.destroy(); return result

        def add_image(self,*_):
            source=self.choose_file("Add static wallpaper",["*.png","*.jpg","*.jpeg","*.webp","*.bmp","*.gif"])
            if source:
                try: p=import_media(source,IMAGE_EXTS); self.refresh(); self.status.set_text(f"Added image: {p.name}")
                except WallpaperError as e: self.alert(str(e))

        def add_video(self,*_):
            source=self.choose_file("Add live video wallpaper",["*.mp4","*.mkv","*.webm","*.mov","*.avi","*.m4v","*.ogv"])
            if source:
                try: p=import_media(source,VIDEO_EXTS); self.refresh(); self.status.set_text(f"Added live video: {p.name}")
                except WallpaperError as e: self.alert(str(e))

        def refresh(self):
            self.image_store.clear(); self.video_store.clear(); LIBRARY.mkdir(parents=True,exist_ok=True)
            for path in sorted(LIBRARY.iterdir(),key=lambda p:p.name.lower()):
                if not path.is_file(): continue
                if path.suffix.lower() in IMAGE_EXTS:
                    try: self.image_store.append([GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path),220,130,True),path.name,str(path)])
                    except Exception: pass
                elif path.suffix.lower() in VIDEO_EXTS: self.video_store.append([path.name,str(path)])
            self.status.set_text(f"{len(self.image_store)} images • {len(self.video_store)} videos • {LIBRARY}")

        def select_image(self,*_):
            rows=self.image_view.get_selected_items()
            if not rows: self.selected_image=None; return
            self.selected_image=Path(self.image_store[rows[0]][2])
            try: self.preview.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_scale(str(self.selected_image),400,260,True))
            except Exception: pass
            self.image_info.set_text(self.selected_image.name)

        def select_video(self,selection):
            model,iterator=selection.get_selected()
            self.selected_video=Path(model[iterator][1]) if iterator else None
            self.video_info.set_text(self.selected_video.name if self.selected_video else "Select a video wallpaper")

        def apply_selected(self,*_):
            if not self.selected_image: self.alert("Select an image first.",Gtk.MessageType.INFO); return
            try: apply(self.selected_image,self.mode.get_active_id() or "zoomed"); self.status.set_text(f"Applied static wallpaper: {self.selected_image.name}")
            except WallpaperError as e: self.alert(str(e))

        def start_video(self,*_):
            if not self.selected_video: self.alert("Select a video first.",Gtk.MessageType.INFO); return
            try:
                args=["start",self.selected_video,"--volume",int(self.volume.get_value())]
                if not self.audio.get_active(): args.append("--no-audio")
                if self.restore_live.get_active(): args.append("--restore-on-login")
                output=engine(*args)
                self.status.set_text(output)
            except WallpaperError as e: self.alert(str(e))

        def toggle_pause(self,*_):
            try: self.status.set_text(engine("toggle"))
            except WallpaperError as e: self.alert(str(e))

        def restart_video(self,*_):
            try: self.status.set_text(engine("restart"))
            except WallpaperError as e: self.alert(str(e))

        def volume_changed(self,scale):
            if not LIVE_CONFIG.is_file(): return
            try:
                engine("volume",int(scale.get_value()),check=False)
            except WallpaperError:
                pass

        def audio_changed(self,button):
            if not LIVE_CONFIG.is_file(): return
            try:
                self.status.set_text(engine("audio","on" if button.get_active() else "off"))
            except WallpaperError:
                pass

        def stop_video(self,*_):
            try:
                engine("stop")
                self.status.set_text("Live wallpaper stopped • XFCE desktop icons restored")
            except WallpaperError as e: self.alert(str(e))

    Main().show_all(); Gtk.main(); return 0

def main():
    parser=argparse.ArgumentParser(description="XFCE static and live wallpaper control centre")
    group=parser.add_mutually_exclusive_group(); group.add_argument("--restore",action="store_true"); group.add_argument("--adopt-current",action="store_true"); group.add_argument("--gui",action="store_true")
    args=parser.parse_args()
    try:
        if args.restore: restore(); return 0
        if args.adopt_current:
            image=current()
            if not image: raise WallpaperError("XFCE has no valid current wallpaper.")
            apply(image,state().get("mode","zoomed")); print(f"Saved current wallpaper: {image}"); return 0
        return gui()
    except WallpaperError as e: print(f"Wallpaper Control Centre: {e}",file=sys.stderr); return 1

if __name__=="__main__": raise SystemExit(main())
