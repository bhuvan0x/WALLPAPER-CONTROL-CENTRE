#!/usr/bin/env python3
"""Non-destructive MP4 optimizer for Wallpaper Control Centre."""
import os
import shutil
import subprocess
import threading
import uuid
from pathlib import Path


class OptimizerError(RuntimeError):
    pass


def _tool(name):
    path = shutil.which(name)
    if not path:
        raise OptimizerError(f"{name} is not installed. Update the Termux-Debian-X11 setup and install FFmpeg.")
    return path


def _duration(path, ffprobe):
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        text=True, capture_output=True, timeout=20, check=False)
    if result.returncode:
        raise OptimizerError((result.stderr or "FFprobe could not read this MP4.").strip())
    try:
        duration = float(result.stdout.strip())
        return duration if duration > 0 else None
    except (TypeError, ValueError):
        return None


def optimize_video(source, output_dir, progress=None):
    """Create a new H.264/AAC copy; never replace or delete the source."""
    source = Path(source).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".mp4":
        raise OptimizerError("Choose an existing MP4 file.")
    if source.stat().st_size == 0:
        raise OptimizerError("The source MP4 is empty.")

    ffmpeg, ffprobe = _tool("ffmpeg"), _tool("ffprobe")
    duration = _duration(source, ffprobe)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{source.stem}.optimized.mp4"
    index = 2
    while output.exists():
        output = output_dir / f"{source.stem}.optimized-{index}.mp4"
        index += 1
    temporary = output_dir / f".{source.stem}.{uuid.uuid4().hex}.partial.mp4"

    command = [
        ffmpeg, "-hide_banner", "-nostdin", "-y", "-i", str(source),
        "-map", "0:v:0", "-map", "0:a?", "-sn", "-dn",
        "-vf", "scale=w='min(1920,iw)':h='min(1080,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,fps='min(30,source_fps)'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", "-map_metadata", "-1",
        "-progress", "pipe:1", "-nostats", str(temporary),
    ]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, bufsize=1)
        errors = []

        def drain_errors():
            for line in process.stderr:
                errors.append(line.rstrip())
                if len(errors) > 80:
                    del errors[:20]

        reader = threading.Thread(target=drain_errors, daemon=True)
        reader.start()
        for line in process.stdout:
            key, separator, value = line.strip().partition("=")
            if progress and separator and key == "out_time_ms" and duration:
                try:
                    percent = max(0.0, min(99.0, int(value) / 1000000 / duration * 100))
                    progress(percent)
                except ValueError:
                    pass
        code = process.wait()
        reader.join(timeout=2)
        if code:
            raise OptimizerError("\n".join(errors[-12:]).strip() or f"FFmpeg exited with status {code}.")
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise OptimizerError("FFmpeg finished without producing a valid output file.")
        os.replace(temporary, output)
    except (OSError, subprocess.SubprocessError) as exc:
        raise OptimizerError(str(exc)) from exc
    finally:
        temporary.unlink(missing_ok=True)

    original_bytes, output_bytes = source.stat().st_size, output.stat().st_size
    saved = original_bytes - output_bytes
    return {
        "source": source, "output": output,
        "original_bytes": original_bytes, "output_bytes": output_bytes,
        "saved_bytes": saved,
        "saved_percent": saved / original_bytes * 100 if original_bytes else 0.0,
    }
