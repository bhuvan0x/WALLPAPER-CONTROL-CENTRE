#!/usr/bin/env python3
"""Local static wallpaper manager for XFCE."""
import argparse, json, os, shutil, subprocess, sys, uuid
from pathlib import Path
HOME=Path.home(); LIBRARY=HOME/"Pictures"/"Wallpapers"
CONFIG=HOME/".config"/"wallpaper-control-centre"/"state.json"
EXTS={".png",".jpg",".jpeg",".webp",".bmp",".gif"}
MODES={"none":0,"centered":1,"tiled":2,"stretched":3,"scaled":4,"zoomed":5,"spanned":6}
CHANNEL="xfce4-desktop"
class WallpaperError(RuntimeError): pass
def query(*args,check=True):
    try: p=subprocess.run(["xfconf-query","-c",CHANNEL,*args],text=True,capture_output=True)
    except FileNotFoundError as e: raise WallpaperError("xfconf-query is unavailable.") from e
    if check and p.returncode: raise WallpaperError((p.stderr or p.stdout).strip() or "XFCE rejected the setting.")
    return p
def properties():
    p=query("-l",check=False)
    found=[x.strip() for x in p.stdout.splitlines() if x.strip().endswith("/last-image")]
    return found or ["/backdrop/screen0/monitor0/workspace0/last-image"]
def current():
    for prop in properties():
        p=query("-p",prop,check=False); value=p.stdout.strip()
        if p.returncode==0 and value and Path(value).is_file(): return Path(value).expanduser().resolve()
    return None
def state():
    try:
        obj=json.loads(CONFIG.read_text(encoding="utf-8")); return obj if isinstance(obj,dict) else {}
    except (OSError,ValueError): return {}
def save(path,mode):
    CONFIG.parent.mkdir(parents=True,exist_ok=True); tmp=CONFIG.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version":1,"image":str(path.resolve()),"mode":mode},indent=2)+"\n",encoding="utf-8")
    os.replace(tmp,CONFIG)
def apply(path,mode="zoomed",persist=True):
    path=path.expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in EXTS: raise WallpaperError(f"Unsupported or missing image: {path}")
    if mode not in MODES: mode="zoomed"
    for prop in properties():
        query("-p",prop,"--create","-t","string","-s",str(path))
        query("-p",prop[:-len("last-image")]+"image-style","--create","-t","int","-s",str(MODES[mode]))
    if persist: save(path,mode)
def restore():
    data=state(); saved=Path(data["image"]).expanduser() if data.get("image") else None; mode=data.get("mode","zoomed")
    if saved and saved.is_file(): apply(saved,mode,False); print(f"Restored wallpaper: {saved}"); return
    # First-run migration: preserve the image XFCE already has selected.
    selected=current()
    if selected: apply(selected,mode,True); print(f"Adopted current XFCE wallpaper: {selected}"); return
    fallback=HOME/".local/share/backgrounds/WhiteSur-wallpaper.png"
    if fallback.is_file(): apply(fallback,"zoomed",True); print(f"Initialized with WhiteSur fallback: {fallback}"); return
    raise WallpaperError("No saved wallpaper or valid XFCE wallpaper. Open the manager and add an image.")
def import_image(source):
    source=source.expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in EXTS: raise WallpaperError("Choose PNG, JPG, JPEG, WEBP, BMP or GIF.")
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
            super().__init__(title="Wallpaper Control Centre"); self.set_default_size(900,580); self.set_border_width(18); self.selected=None
            root=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12); self.add(root)
            title=Gtk.Label(); title.set_markup("<span size='xx-large' weight='bold'>Wallpaper Control Centre</span>"); title.set_xalign(0); root.pack_start(title,False,False,0)
            note=Gtk.Label(label="A personal wallpaper library, with reliable desktop restoration."); note.set_xalign(0); root.pack_start(note,False,False,0)
            body=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=16); root.pack_start(body,True,True,0)
            self.store=Gtk.ListStore(GdkPixbuf.Pixbuf,str,str); self.view=Gtk.IconView.new(); self.view.set_model(self.store); self.view.set_pixbuf_column(0); self.view.set_text_column(1); self.view.set_item_width(150); self.view.set_spacing(12); self.view.connect("selection-changed",self.select)
            scroll=Gtk.ScrolledWindow(); scroll.add(self.view); body.pack_start(scroll,True,True,0)
            side=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10); side.set_size_request(220,-1); body.pack_start(side,False,False,0)
            self.preview=Gtk.Image(); self.preview.set_size_request(200,130); side.pack_start(self.preview,False,False,0)
            self.info=Gtk.Label(label="Select an image"); self.info.set_line_wrap(True); self.info.set_xalign(0); side.pack_start(self.info,False,False,0)
            side.pack_start(Gtk.Label(label="Display mode",xalign=0),False,False,0); self.mode=Gtk.ComboBoxText()
            for key,label in [("zoomed","Zoom / Fill"),("scaled","Scale / Fit"),("stretched","Stretch"),("centered","Center"),("tiled","Tile"),("spanned","Span")]: self.mode.append(key,label)
            self.mode.set_active_id(state().get("mode","zoomed")); side.pack_start(self.mode,False,False,0)
            for label,callback in [("＋  Add wallpaper",self.on_add_wallpaper),("Set as desktop wallpaper",self.apply_selected),("Refresh library",lambda *_:self.refresh())]:
                button=Gtk.Button(label=label); button.connect("clicked",callback); side.pack_start(button,False,False,0)
            self.status=Gtk.Label(label=str(LIBRARY)); self.status.set_xalign(0); self.status.set_line_wrap(True); root.pack_end(self.status,False,False,0)
            self.refresh(); self.connect("destroy",Gtk.main_quit)
        def refresh(self):
            self.store.clear(); LIBRARY.mkdir(parents=True,exist_ok=True)
            for path in sorted(LIBRARY.iterdir(),key=lambda p:p.name.lower()):
                if path.is_file() and path.suffix.lower() in EXTS:
                    try: self.store.append([GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path),220,130,True),path.name,str(path)])
                    except Exception: pass
            self.status.set_text(f"{len(self.store)} wallpapers • {LIBRARY}")
        def select(self,*_):
            rows=self.view.get_selected_items()
            if not rows: self.selected=None; return
            self.selected=Path(self.store[rows[0]][2])
            try: self.preview.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_scale(str(self.selected),400,260,True))
            except Exception: pass
            self.info.set_text(self.selected.name)
        def alert(self,message,kind=Gtk.MessageType.ERROR):
            d=Gtk.MessageDialog(transient_for=self,flags=Gtk.DialogFlags.MODAL,message_type=kind,buttons=Gtk.ButtonsType.CLOSE,text=message); d.run(); d.destroy()
        def on_add_wallpaper(self,*_):
            d=Gtk.FileChooserDialog(title="Add wallpaper",parent=self,action=Gtk.FileChooserAction.OPEN); d.add_buttons("Cancel",Gtk.ResponseType.CANCEL,"Add",Gtk.ResponseType.ACCEPT)
            f=Gtk.FileFilter(); f.set_name("Images")
            for pattern in ("*.png","*.jpg","*.jpeg","*.webp","*.bmp","*.gif"): f.add_pattern(pattern)
            d.add_filter(f)
            if d.run()==Gtk.ResponseType.ACCEPT:
                try: p=import_image(Path(d.get_filename())); self.refresh(); self.status.set_text(f"Added {p.name}")
                except WallpaperError as e: self.alert(str(e))
            d.destroy()
        def apply_selected(self,*_):
            if not self.selected: self.alert("Select a wallpaper first.",Gtk.MessageType.INFO); return
            try: apply(self.selected,self.mode.get_active_id() or "zoomed"); self.status.set_text(f"Applied and saved: {self.selected.name}")
            except WallpaperError as e: self.alert(str(e))
    Main().show_all(); Gtk.main(); return 0
def main():
    parser=argparse.ArgumentParser(description="XFCE wallpaper library and restore controller")
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
