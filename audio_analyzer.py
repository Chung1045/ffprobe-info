import subprocess
import json
import numpy as np
import re

class AudioAnalyzer:
    def __init__(self):
        self.target_lufs = -14.0  # Standard streaming target LUFS
        
    def get_lufs(self, file_path):
        try:
            # First return a processing message
            analysis = "LOUDNESS ANALYSIS\n"
            analysis += "-" * 30 + "\n"
            analysis += "Processing... Please wait...\n"
            
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
                input_tp = float(stats.get('input_tp', 0))    # True peak
                
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