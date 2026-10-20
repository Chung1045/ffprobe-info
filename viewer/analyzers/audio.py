import json

from .. import ffmpeg_tools


class AudioAnalyzer:
    TARGET_LUFS = -14.0  # common streaming target
    TOLERANCE_DB = 2.0

    def get_lufs(self, file_path: str) -> str:
        """Blocking loudness analysis. Call it from a background thread, not the UI thread."""
        ffmpeg = ffmpeg_tools.find_tool("ffmpeg")
        if not ffmpeg:
            return "Error analyzing audio: ffmpeg not found"
        try:
            result = ffmpeg_tools.run([
                ffmpeg, "-nostdin", "-hide_banner", "-i", file_path,
                "-vn",  # skip video decoding: much faster on video files
                "-af", f"loudnorm=print_format=json:I={self.TARGET_LUFS:.0f}:LRA=11:TP=-1.5",
                "-f", "null", "-",
            ])
            # loudnorm prints a flat JSON object at the very end of stderr
            start, end = result.stderr.rfind("{"), result.stderr.rfind("}")
            if start == -1 or end < start:
                return "Could not analyze audio loudness"
            return self._format(json.loads(result.stderr[start:end + 1]))
        except Exception as e:
            return f"Error analyzing audio: {e}"

    def _format(self, stats: dict) -> str:
        lufs = float(stats.get("input_i", 0))
        lra = float(stats.get("input_lra", 0))
        true_peak = float(stats.get("input_tp", 0))

        text = "\nLOUDNESS ANALYSIS\n" + "-" * 30 + "\n"
        text += f"Average LUFS: {lufs:.1f} LUFS\n"
        text += f"Loudness Range: {lra:.1f} LU\n"
        text += f"True Peak: {true_peak:.1f} dBTP\n"

        if lufs == float("-inf"):
            return text + "The audio source is silent"

        diff = abs(lufs - self.TARGET_LUFS)
        if diff <= self.TOLERANCE_DB:
            return text + "[GOOD] Audio loudness is within streaming standards"
        if lufs > self.TARGET_LUFS:
            return (text + "[HIGH] Audio is louder than streaming target (-14 LUFS)\n"
                    f"Recommend reducing volume by {diff:.1f} dB")
        return (text + "[LOW] Audio is quieter than streaming target (-14 LUFS)\n"
                f"Recommend increasing volume by {diff:.1f} dB")
