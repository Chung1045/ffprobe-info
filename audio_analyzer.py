import subprocess
import json
import numpy as np
import re
import threading
from concurrent.futures import ThreadPoolExecutor


class AudioAnalyzer:
    def __init__(self):
        self.target_lufs = -14.0  # Standard streaming target LUFS

    def get_lufs(self, file_path, callback=None):
        """
        Non-blocking method to get LUFS values.
        If callback is provided, analysis will run in background and callback will be called with results.
        If no callback is provided, returns a processing message.
        """
        # Return immediately with processing message
        initial_message = "LOUDNESS ANALYSIS\n" + "-" * 30 + "\n" + "Processing... Please wait...\n"

        if callback:
            # Start analysis in a background thread
            def run_analysis():
                result = self._analyze_audio(file_path)
                callback(result)

            threading.Thread(target=run_analysis).start()
            return initial_message
        else:
            # Synchronous mode (for backwards compatibility)
            return self._analyze_audio(file_path)

    def get_lufs_async(self, file_path):
        """
        Returns a Future that will contain the result when analysis is complete.
        Use with: future = analyzer.get_lufs_async(file_path)
                  result = future.result()  # will block until complete
        """
        with ThreadPoolExecutor() as executor:
            return executor.submit(self._analyze_audio, file_path)

    def _analyze_audio(self, file_path):
        """Internal method that performs the actual audio analysis"""
        try:
            # Run ffmpeg with loudnorm filter to get loudness stats
            command = [
                'ffmpeg',
                '-i', file_path,
                '-af', 'loudnorm=print_format=json:I=-14:LRA=11:TP=-1.5',
                '-f', 'null',
                '-'
            ]

            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')

            # Extract JSON data from ffmpeg output
            match = re.search(r'\{.*\}', result.stderr, re.DOTALL)
            if match:
                stats = json.loads(match.group())

                input_lufs = float(stats.get('input_i', 0))
                input_lra = float(stats.get('input_lra', 0))  # Loudness range
                input_tp = float(stats.get('input_tp', 0))  # True peak

                # Format the final analysis
                analysis = "\nLOUDNESS ANALYSIS\n"
                analysis += "-" * 30 + "\n"
                analysis += f"Average LUFS: {input_lufs:.1f} LUFS\n"
                analysis += f"Loudness Range: {input_lra:.1f} LU\n"
                analysis += f"True Peak: {input_tp:.1f} dBTP\n"

                if input_lufs == float('-inf'):
                    analysis += "The audio source is silent"
                    return analysis
                else:
                    # Add recommendation based on streaming target
                    diff = abs(input_lufs - self.target_lufs)
                    if diff > 2.0:
                        if input_lufs > self.target_lufs:
                            analysis += f"[HIGH] Audio is louder than streaming target (-14 LUFS)\n"
                            analysis += f"Recommend reducing volume by {diff:.1f} dB"
                        else:
                            analysis += f"[LOW] Audio is quieter than streaming target (-14 LUFS)\n"
                            analysis += f"Recommend increasing volume by {diff:.1f} dB"
                    else:
                        analysis += "[GOOD] Audio loudness is within streaming standards"

                    return analysis

            return "Could not analyze audio loudness"

        except Exception as e:
            return f"Error analyzing audio: {str(e)}"