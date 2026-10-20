"""Everything that talks to ffmpeg / ffprobe lives here (one place to fix paths, flags, errors)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from .resources import resource_path

# Stops a console window flashing up for every subprocess in a windowed Windows build.
# On macOS/Linux this attribute doesn't exist, so it falls back to 0 (no-op).
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# GUI apps launched from Finder don't inherit your shell PATH, so Homebrew's ffmpeg isn't found.
_EXTRA_SEARCH_DIRS = ["/opt/homebrew/bin", "/usr/local/bin"] if sys.platform == "darwin" else []

class FFmpegError(Exception):
    pass

def find_tool(name: str):
    """Return the full path of ffmpeg/ffprobe: bundled copy first, then PATH."""
    exe = name + (".exe" if sys.platform == "win32" else "")
    bundled = resource_path("bin", exe)
    if bundled.exists():
        return str(bundled)
    search_path = os.pathsep.join([os.environ.get("PATH", ""), *_EXTRA_SEARCH_DIRS])
    return shutil.which(name, path=search_path)


def ffmpeg_available() -> bool:
    return bool(find_tool("ffmpeg") and find_tool("ffprobe"))


def run(cmd):
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=_NO_WINDOW,
    )


def probe(file_path: str) -> dict:
    """Run ffprobe once and return the parsed JSON."""
    ffprobe = find_tool("ffprobe")
    if not ffprobe:
        raise FFmpegError("FFmpeg/FFprobe not found. Please install FFmpeg.")
    result = run([ffprobe, "-v", "quiet", "-print_format", "json",
                  "-show_format", "-show_streams", file_path])
    if result.returncode != 0:
        raise FFmpegError(f"Unable to read metadata from {file_path}")
    return json.loads(result.stdout)


def extract_thumbnail(file_path: str):
    """Return image bytes of embedded album art or the first video frame, else None."""
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "thumb.jpg")
        attempts = (
            # 1) embedded cover / album art
            [ffmpeg, "-nostdin", "-y", "-i", file_path, "-an", "-vcodec", "copy", out],
            # 2) first frame of a video
            [ffmpeg, "-nostdin", "-y", "-i", file_path, "-vframes", "1", "-vf", "scale=-1:150", out],
        )
        for cmd in attempts:
            result = run(cmd)
            if result.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 0:
                with open(out, "rb") as f:
                    return f.read()
    return None
