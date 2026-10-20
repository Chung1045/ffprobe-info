"""Turn ffprobe JSON into the text shown in each tab. Pure functions: no Qt, easy to test."""
import json

from .analyzers import VideoQualityAnalyzer

SEP = "=" * 50
IMAGE_CODECS = {"mjpeg", "jpeg", "png", "bmp"}  # cover art / stills, not real video

_quality = VideoQualityAnalyzer()


# ---------- helpers ----------
def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _kbps(value) -> float:
    return _to_float(value) / 1000


def is_video_stream(stream: dict) -> bool:
    return (stream.get("codec_type") == "video"
            and not stream.get("disposition", {}).get("attached_pic")
            and stream.get("codec_name", "").lower() not in IMAGE_CODECS)


def file_type(metadata: dict) -> str:
    return "video" if any(is_video_stream(s) for s in metadata.get("streams", [])) else "audio"


def _video_bitrate_kbps(stream, format_info, streams) -> float:
    if stream.get("bit_rate"):
        return _kbps(stream["bit_rate"])
    audio = sum(_kbps(s.get("bit_rate")) for s in streams if s.get("codec_type") == "audio")
    return _kbps(format_info.get("bit_rate")) - audio


# ---------- one function per tab ----------
def format_overview(metadata: dict) -> str:
    info = metadata.get("format", {})
    lines = [
        "📁 FILE INFORMATION", SEP,
        f"Type: {file_type(metadata).title()} File",
        f"Filename: {info.get('filename', 'N/A')}",
        f"Format: {info.get('format_name', 'N/A')}",
        f"Duration: {_to_float(info.get('duration')):.2f} seconds",
        f"Size: {_to_float(info.get('size')) / (1024 * 1024):.2f} MB",
        f"Bitrate: {_kbps(info.get('bit_rate')):.2f} kbps",
    ]
    tags = info.get("tags", {})
    if tags:
        lines += ["", "📌 TAGS", SEP]
        lines += [f"{key.title()}: {value}" for key, value in tags.items()]
    return "\n".join(lines) + "\n"


def format_video(metadata: dict) -> str:
    info, streams = metadata.get("format", {}), metadata.get("streams", [])
    video_streams = [s for s in streams if is_video_stream(s)]
    if not video_streams:
        return "No video streams found."

    lines = ["🎥 VIDEO STREAMS", SEP]
    for i, stream in enumerate(video_streams, 1):
        codec = stream.get("codec_name", "N/A").lower()
        resolution = f"{stream.get('width', 'N/A')}x{stream.get('height', 'N/A')}"
        framerate = stream.get("r_frame_rate", "30/1")
        bitrate = _video_bitrate_kbps(stream, info, streams)

        lines += [
            f"Video Stream #{i}",
            f"  Codec: {codec.upper()}",
            f"  Resolution: {resolution}",
            f"  Framerate: {framerate}",
            f"  Pixel Format: {stream.get('pix_fmt', 'N/A')}",
        ]
        if bitrate > 0:
            lines += [
                f"  Bitrate: {bitrate:.2f} kbps", "",
                "  📊 QUALITY ANALYSIS", "  " + "-" * 30,
                f"  {_quality.analyze_video_quality(resolution, bitrate, codec, framerate)}",
            ]
        lines.append("")
    return "\n".join(lines)


def format_audio(metadata: dict, loudness: str = None) -> str:
    streams = [s for s in metadata.get("streams", []) if s.get("codec_type") == "audio"]
    if not streams:
        return "No audio streams found."

    lines = ["🔊 AUDIO STREAMS", SEP]
    for i, stream in enumerate(streams, 1):
        lines += [
            f"Audio Stream #{i}",
            f"  Codec: {stream.get('codec_name', 'N/A')}",
            f"  Channels: {stream.get('channels', 'N/A')}",
            f"  Sample Rate: {stream.get('sample_rate', 'N/A')} Hz",
        ]
        if stream.get("bit_rate"):
            lines.append(f"  Bitrate: {_kbps(stream['bit_rate']):.2f} kbps")
        if i == 1 and loudness:  # loudness is measured on the first audio stream
            lines += ["", "  📊 LOUDNESS ANALYSIS", "  " + "-" * 30]
            for line in loudness.splitlines():
                line = line.strip()
                if line and line != "LOUDNESS ANALYSIS" and set(line) != {"-"}:
                    lines.append(f"  {line}")
        lines.append("")
    return "\n".join(lines)


def format_subtitles(metadata: dict) -> str:
    streams = [s for s in metadata.get("streams", []) if s.get("codec_type") == "subtitle"]
    if not streams:
        return "No subtitle streams found."

    lines = ["💬 SUBTITLE STREAMS", SEP]
    for i, stream in enumerate(streams, 1):
        lines += [
            f"Subtitle Stream #{i}",
            f"  Codec: {stream.get('codec_name', 'N/A')}",
            f"  Language: {stream.get('tags', {}).get('language', 'N/A')}",
            "",
        ]
    return "\n".join(lines)


def format_all(metadata: dict) -> dict:
    """Text for every tab, keyed by tab id."""
    try:
        return {
            "overview": format_overview(metadata),
            "video": format_video(metadata),
            "audio": format_audio(metadata),
            "subtitles": format_subtitles(metadata),
            "raw": json.dumps(metadata, indent=2),
        }
    except Exception as e:
        msg = f"Error formatting metadata: {e}"
        return {key: msg for key in ("overview", "video", "audio", "subtitles", "raw")}
