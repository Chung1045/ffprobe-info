class VideoQualityAnalyzer:
    def __init__(self):
        # Base recommended minimum bitrates (in kbps) for H.264/AVC at 30fps
        self.h264_quality_tiers = {
            3840*2160: 35000,  # 4K
            2560*1440: 16000,  # 2K/1440p
            1920*1080: 8000,   # 1080p
            1280*720: 5000,    # 720p
            854*480: 2500,     # 480p
            640*360: 1000,     # 360p
            426*240: 600       # 240p
        }
        
        # Codec efficiency multipliers (relative to H.264)
        # Including common codec name variations from ffmpeg
        self.codec_multipliers = {
            # H.264 / AVC
            'h264': 1.0,
            'avc': 1.0,
            'avc1': 1.0,
            'h.264': 1.0,
            'libx264': 1.0,
            
            # H.265 / HEVC
            'h265': 0.5,
            'hevc': 0.5,
            'h.265': 0.5,
            'libx265': 0.5,
            
            # VP9
            'vp9': 0.6,
            'libvpx-vp9': 0.6,
            
            # AV1
            'av1': 0.45,
            'libaom-av1': 0.45,
            'svt-av1': 0.45,
            
            # VP8 (older, less efficient)
            'vp8': 1.2,
            'libvpx': 1.2,
            
            # MPEG4
            'mpeg4': 1.4,
            'mp4v': 1.4,
            
            # MPEG2
            'mpeg2video': 1.6,
            'mpeg2': 1.6,
            
            # Default for unknown codecs
            'default': 1.0
        }

    def parse_framerate(self, framerate_str):
        """
        Parse framerate string in format 'num/den' or numeric
        
        Args:
            framerate_str (str): Framerate in format like '30/1', '60000/1001' (59.94), or '25'
            
        Returns:
            float: Framerate as a float number
        """
        try:
            if '/' in framerate_str:
                num, den = map(float, framerate_str.split('/'))
                return num / den if den != 0 else 0
            return float(framerate_str)
        except (ValueError, ZeroDivisionError, AttributeError):
            return 0

    def get_framerate_multiplier(self, fps):
        """
        Calculate bitrate multiplier based on framerate
        Base reference is 30fps, scales roughly linearly but with diminishing returns
        
        Args:
            fps (float): Frames per second
            
        Returns:
            float: Multiplier for bitrate
        """
        if fps <= 0:
            return 1.0
            
        # Base reference is 30fps
        # Use a slightly sub-linear scale for higher framerates
        # This reflects that doubling the framerate doesn't quite need double the bitrate
        return (fps / 30) ** 0.93

    def get_recommended_bitrate(self, resolution, codec_name, framerate):
        """
        Calculate recommended bitrate based on resolution, codec and framerate
        
        Args:
            resolution (str): Video resolution in format 'widthxheight'
            codec_name (str): Video codec name (e.g., 'h264', 'hevc')
            framerate (str): Framerate string (e.g., '30/1', '60000/1001')
            
        Returns:
            tuple: (recommended_bitrate, codec_multiplier, fps_multiplier, actual_fps)
        """
        width, height = map(int, resolution.split('x'))
        pixels = width * height
        
        # Find the closest resolution tier
        closest_tier = min(self.h264_quality_tiers.keys(), 
                         key=lambda x: abs(x - pixels))
        base_bitrate = self.h264_quality_tiers[closest_tier]
        
        # Get codec multiplier (default to 1.0 if codec not recognized)
        codec_name = codec_name.lower().strip()
        codec_multiplier = self.codec_multipliers.get(codec_name, 
                                                    self.codec_multipliers['default'])
        
        # Calculate framerate multiplier
        actual_fps = self.parse_framerate(framerate)
        fps_multiplier = self.get_framerate_multiplier(actual_fps)
        
        # Calculate final bitrate
        recommended_bitrate = base_bitrate * codec_multiplier * fps_multiplier
        
        return recommended_bitrate, codec_multiplier, fps_multiplier, actual_fps

    def analyze_video_quality(self, resolution, bitrate_kbps, codec_name, framerate):
        """
        Analyze if video bitrate is sufficient for the resolution, codec and framerate
        
        Args:
            resolution (str): Video resolution in format 'widthxheight'
            bitrate_kbps (float): Video bitrate in kbps
            codec_name (str): Video codec name (e.g., 'h264', 'hevc')
            framerate (str): Framerate string (e.g., '30/1', '60000/1001')
            
        Returns:
            str: Quality analysis result with recommendation
        """
        try:
            width, height = map(int, resolution.split('x'))
            recommended_bitrate, codec_multiplier, fps_multiplier, actual_fps = \
                self.get_recommended_bitrate(resolution, codec_name, framerate)
            
            # Create codec info string
            codec_info = f"({codec_name.upper()}"
            if codec_multiplier != 1.0:
                if codec_multiplier < 1.0:
                    codec_info += f", {(1/codec_multiplier):.1f}x more efficient than H.264"
                else:
                    codec_info += f", {codec_multiplier:.1f}x less efficient than H.264"
            if actual_fps > 0:
                codec_info += f", {actual_fps:.1f}fps"
                if fps_multiplier != 1.0:
                    codec_info += f", {fps_multiplier:.1f}x bitrate multiplier"
            codec_info += ")"
            
            # Analyze quality
            if bitrate_kbps < recommended_bitrate * 0.6:  # Significantly under recommended
                return (f"[LOW] Bitrate for {width}x{height} {codec_info}: "
                       f"{bitrate_kbps:.0f} kbps (Recommended: {recommended_bitrate:.0f} kbps)")
            elif bitrate_kbps < recommended_bitrate * 0.8:  # Slightly under recommended
                return (f"[MODERATE] Bitrate for {width}x{height} {codec_info}: "
                       f"{bitrate_kbps:.0f} kbps (Recommended: {recommended_bitrate:.0f} kbps)")
            else:  # Good bitrate
                return (f"[GOOD] Bitrate for {width}x{height} {codec_info}: "
                       f"{bitrate_kbps:.0f} kbps")
        except Exception as e:
            return f"Error analyzing video quality: {str(e)}"