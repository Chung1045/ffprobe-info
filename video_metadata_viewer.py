import json
import os
import shutil
import subprocess
import sys
import tempfile

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap, QFontDatabase
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout,
                             QTextEdit, QWidget, QFileDialog, QLabel, QHBoxLayout,
                             QMessageBox)

from audio_analyzer import AudioAnalyzer
from video_quality_analyzer import VideoQualityAnalyzer


class QCollapsibleBox(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.toggle_button = QPushButton(title, self)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 5px;
                background: #2b2b2b;
                border: none;
                color: #dcdcdc;
            }
            QPushButton:hover {
                background: #3b3b3b;
            }
        """)
        self.toggle_button.clicked.connect(self.on_toggle)

        self.content = QTextEdit(self)
        self.content.setReadOnly(True)
        self.content.hide()

        layout = QVBoxLayout(self)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.content)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

    def on_toggle(self):
        self.content.setVisible(not self.content.isVisible())

    def setText(self, text):
        self.content.setText(text)


class DropLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setText("Drop video file here\nor click to select file")
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaa;
                border-radius: 5px;
                padding: 20px;
                background: #f0f0f0;
            }
            QLabel:hover {
                background: #e0e0e0;
                border-color: #999;
            }
        """)
        self.setFixedHeight(100)  # Smaller fixed height
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            self.parent().parent().display_metadata(files[0])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.parent().parent().select_file()


class VideoMetadataViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        if not self.check_ffmpeg():
            self.show_ffmpeg_error()
            sys.exit(1)

        self.setWindowTitle("Media Metadata Viewer")
        self.setGeometry(100, 100, 1200, 800)
        self.setAcceptDrops(True)  # Enable drops for main window
        self.min_width_for_horizontal = 1000  # Minimum width for horizontal layout
        self.setup_ui()
        self.current_thumbnail = None
        self.quality_analyzer = VideoQualityAnalyzer()
        self.audio_analyzer = AudioAnalyzer()
        self.lufs_timer = QTimer()
        self.lufs_timer.setSingleShot(True)
        self.lufs_timer.timeout.connect(self.process_lufs_analysis)
        self.current_file = None  # To store current file path

    def check_ffmpeg(self):
        """Check if ffmpeg and ffprobe are installed"""
        return (shutil.which('ffmpeg') is not None and
                shutil.which('ffprobe') is not None)

    def show_ffmpeg_error(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("FFmpeg Not Found")

        error_text = "FFmpeg is required but not found on your system.\n\n"
        error_text += "Please install FFmpeg:\n\n"

        if sys.platform == "darwin":  # macOS
            error_text += "Using Homebrew:\n"
            error_text += "1. Install Homebrew from https://brew.sh\n"
            error_text += "2. Run: brew install ffmpeg\n"
        elif sys.platform == "win32":  # Windows
            error_text += "1. Download FFmpeg from https://ffmpeg.org/download.html\n"
            error_text += "2. Extract the archive\n"
            error_text += "3. Add FFmpeg's bin folder to your system's PATH\n"
        else:  # Linux
            error_text += "Using apt (Ubuntu/Debian):\n"
            error_text += "sudo apt update && sudo apt install ffmpeg\n\n"
            error_text += "Using dnf (Fedora):\n"
            error_text += "sudo dnf install ffmpeg"

        msg.setText(error_text)
        msg.exec_()

    def setup_ui(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: #2b2b2b;
                color: #dcdcdc;
            }}
            QTextEdit {{
                background-color: #1e1e1e;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-size: 12px;
            }}
        """)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(20)

        # Add usage tips at the start
        self.tips_label = QLabel()
        self.tips_label.setWordWrap(True)
        self.tips_label.setStyleSheet("""
            QLabel {
                color: #a0a0a0;
                padding: 10px;
                background-color: #1e1e1e;
                border-radius: 5px;
            }
        """)
        self.tips_label.setText(
            "💡 Tips:\n"
            "• Drag and drop any media file anywhere on this window\n"
            "• Or click the 'Select Media File' button\n"
            "• Supports video (mp4, avi, mkv, etc.) and audio (mp3, wav, m4a, etc.)\n"
            "• LUFS analysis will be performed automatically for audio streams"
        )
        self.main_layout.addWidget(self.tips_label)

        # Container for horizontal layout
        self.horizontal_container = QWidget()
        self.horizontal_layout = QHBoxLayout(self.horizontal_container)
        self.horizontal_layout.setContentsMargins(0, 0, 0, 0)
        self.horizontal_layout.setSpacing(20)

        # Right panel for thumbnail and controls
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # Thumbnail section
        self.thumbnail_widget = QWidget()
        thumbnail_layout = QVBoxLayout(self.thumbnail_widget)
        thumbnail_layout.setAlignment(Qt.AlignHCenter)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setMinimumSize(150, 150)  # Set minimum size
        self.thumbnail_label.setMaximumSize(200, 200)  # Set maximum size
        self.thumbnail_label.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border-radius: 5px;
            }
        """)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)

        self.file_name_label = QLabel()
        self.file_name_label.setAlignment(Qt.AlignCenter)
        self.file_name_label.setWordWrap(True)
        self.file_name_label.setMinimumWidth(150)  # Minimum width to match thumbnail
        self.file_name_label.setMaximumWidth(200)  # Maximum width to match thumbnail
        self.file_name_label.setStyleSheet("""
            QLabel {
                margin-bottom: 10px;
                padding: 5px;
                font-size: 11px;
                color: #dcdcdc;
            }
        """)

        thumbnail_layout.addWidget(self.thumbnail_label)
        thumbnail_layout.addWidget(self.file_name_label)

        self.right_layout.addWidget(self.thumbnail_widget)

        # Select button
        self.select_button = QPushButton("Select Media File")
        self.select_button.setFixedWidth(120)
        self.select_button.setStyleSheet("""
            QPushButton {
                background-color: #3b3b3b;
                border: none;
                border-radius: 5px;
                padding: 8px;
                color: #dcdcdc;
            }
            QPushButton:hover {
                background-color: #4b4b4b;
            }
        """)
        self.select_button.clicked.connect(self.select_file)
        self.right_layout.addWidget(self.select_button, alignment=Qt.AlignHCenter)

        # Left panel for info
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)

        # Metadata display area
        self.metadata_display = QTextEdit()
        self.metadata_display.setReadOnly(True)
        self.left_layout.addWidget(self.metadata_display)

        # Collapsible raw metadata
        self.raw_metadata_box = QCollapsibleBox("🔧 Raw Metadata (Click to expand)")
        self.left_layout.addWidget(self.raw_metadata_box)

        self.horizontal_layout.addWidget(self.left_panel)
        self.horizontal_layout.addWidget(self.right_panel)

        # Add horizontal container to main layout
        self.main_layout.addWidget(self.horizontal_container)

        # Set initial layout
        self.updateLayout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateLayout()

    def updateLayout(self):
        width = self.width()
        if width < self.min_width_for_horizontal:
            # Switch to vertical layout
            self.horizontal_layout.setDirection(QHBoxLayout.Down)
            self.right_panel.setMaximumWidth(16777215)  # Reset max width
            self.left_panel.setMaximumWidth(16777215)
            # Move right panel to top
            self.right_panel.setParent(None)
            self.main_layout.insertWidget(0, self.right_panel)
        else:
            # Switch to horizontal layout
            self.horizontal_layout.setDirection(QHBoxLayout.LeftToRight)
            self.right_panel.setMaximumWidth(250)  # Limit right panel width
            self.left_panel.setMaximumWidth(16777215)
            # Move right panel back to horizontal container
            self.right_panel.setParent(None)
            self.horizontal_layout.addWidget(self.right_panel)

    def generate_thumbnail(self, file_path):
        if not self.check_ffmpeg():
            self.thumbnail_label.setText("FFmpeg not found")
            self.show_ffmpeg_error()
            return

        try:
            temp_dir = tempfile.gettempdir()
            thumb_path = os.path.join(temp_dir, 'thumb.jpg')

            # Try to extract album art first
            album_art_command = [
                'ffmpeg', '-y', '-i', file_path,
                '-an', '-vcodec', 'copy', thumb_path
            ]

            process = subprocess.run(album_art_command, capture_output=True, encoding='utf-8')

            # If album art extraction fails, generate thumbnail for video
            if process.returncode != 0 or not os.path.exists(thumb_path) or os.path.getsize(thumb_path) == 0:
                video_command = [
                    'ffmpeg', '-y', '-i', file_path,
                    '-vframes', '1', '-vf', 'scale=-1:150',  # Scale to height 150px
                    thumb_path
                ]
                process = subprocess.run(video_command, capture_output=True, encoding='utf-8')

            if process.returncode == 0 and os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
                pixmap = QPixmap(thumb_path)

                # Handle different aspect ratios
                if self.get_file_type(self.get_metadata(file_path)) == 'audio':
                    # For audio files, maintain square aspect for album art
                    size = min(200, max(150, min(pixmap.width(), pixmap.height())))
                    scaled_pixmap = pixmap.scaled(
                        size, size,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                else:
                    # For video files, maintain original aspect ratio
                    if pixmap.width() > pixmap.height():
                        # Landscape: scale to width 200px
                        scaled_pixmap = pixmap.scaledToWidth(200, Qt.SmoothTransformation)
                    else:
                        # Portrait: scale to height 150px
                        scaled_pixmap = pixmap.scaledToHeight(150, Qt.SmoothTransformation)

                self.thumbnail_label.setPixmap(scaled_pixmap)
                # Update filename and title
                filename = os.path.basename(file_path)

                # Get metadata for title
                command = [
                    'ffprobe',
                    '-v', 'quiet',
                    '-print_format', 'json',
                    '-show_format',
                    file_path
                ]

                result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
                try:
                    metadata = json.loads(result.stdout)
                    tags = metadata.get('format', {}).get('tags', {})
                    title = tags.get('title', '')

                    # Handle long filenames
                    max_filename_length = 30
                    if len(filename) > max_filename_length:
                        displayed_filename = filename[:max_filename_length - 3] + "..."
                    else:
                        displayed_filename = filename

                    if title and title != filename:
                        # Handle long titles
                        # if len(title) > max_filename_length:
                        #     displayed_title = title[:max_filename_length-3] + "..."
                        # else:
                        displayed_title = title
                        self.file_name_label.setText(f"{displayed_title}\n({displayed_filename})")
                    else:
                        self.file_name_label.setText(displayed_filename)

                    # Set full name as tooltip
                    if title and title != filename:
                        self.file_name_label.setToolTip(f"{title}\n({filename})")
                    else:
                        self.file_name_label.setToolTip(filename)
                except:
                    self.file_name_label.setText(filename)
                    self.file_name_label.setToolTip(filename)
            else:
                self.thumbnail_label.setText("No thumbnail/album art")
                self.file_name_label.setText(os.path.basename(file_path))

            # Clean up
            if os.path.exists(thumb_path):
                os.remove(thumb_path)

        except Exception as e:
            self.thumbnail_label.setText("Thumbnail error")
            print(f"Thumbnail error: {str(e)}")

    def get_metadata(self, file_path):
        """Get metadata for a file using ffprobe"""
        command = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]

        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {}

    def analyze_video_quality(self, resolution, bitrate_kbps, codec_name, framerate):
        """Analyze if video bitrate is sufficient for the resolution"""
        return self.quality_analyzer.analyze_video_quality(resolution, bitrate_kbps, codec_name, framerate)

    def get_file_type(self, metadata):
        """Determine if the file is video or audio"""
        streams = metadata.get('streams', [])
        # Add VP8/VP9 (WebM codecs) to video detection
        video_codecs = {'h264', 'hevc', 'vp8', 'vp9', 'av1'}
        has_video = any(s.get('codec_type') == 'video' and
                        s.get('codec_name', '').lower() in video_codecs
                        for s in streams)
        return 'video' if has_video else 'audio'

    def format_metadata(self, metadata):
        try:
            format_info = metadata.get('format', {})
            streams = metadata.get('streams', [])
            file_type = self.get_file_type(metadata)

            # Define a standard separator length
            separator_length = 50
            separator = "=" * separator_length + "\n"

            # Basic file information
            formatted = "📁 FILE INFORMATION\n"
            formatted += separator
            formatted += f"Type: {'Video' if file_type == 'video' else 'Audio'} File\n"
            formatted += f"Filename: {format_info.get('filename', 'N/A')}\n"
            formatted += f"Format: {format_info.get('format_name', 'N/A')}\n"
            formatted += f"Duration: {float(format_info.get('duration', 0)):.2f} seconds\n"
            formatted += f"Size: {int(format_info.get('size', 0)) / (1024 * 1024):.2f} MB\n"
            formatted += f"Bitrate: {int(format_info.get('bit_rate', 0)) / 1000:.2f} kbps\n"

            # Add tags if they exist (for audio files)
            tags = format_info.get('tags', {})
            if tags:
                formatted += "\n📌 TAGS\n"
                formatted += separator
                for key, value in tags.items():
                    formatted += f"{key.title()}: {value}\n"
            formatted += "\n"

            # Only show video streams for actual video files
            if file_type == 'video':
                video_streams = [s for s in streams if s.get('codec_type') == 'video'
                                 and s.get('codec_name', '').lower() != 'mjpeg']
                if video_streams:
                    formatted += "🎥 VIDEO STREAMS\n"
                    formatted += separator
                    for i, stream in enumerate(video_streams, 1):
                        formatted += f"Video Stream #{i}\n"
                        codec_name = stream.get('codec_name', 'N/A').lower()  # Get and normalize codec name
                        formatted += f"  Codec: {codec_name.upper()}\n"  # Display in uppercase

                        resolution = f"{stream.get('width', 'N/A')}x{stream.get('height', 'N/A')}"
                        formatted += f"  Resolution: {resolution}\n"

                        framerate = stream.get('r_frame_rate', '30/1')  # Default to 30fps if not specified
                        formatted += f"  Framerate: {framerate}\n"
                        formatted += f"  Pixel Format: {stream.get('pix_fmt', 'N/A')}\n"

                        # Get bitrate either from stream or calculate from format
                        if stream.get('bit_rate'):
                            bitrate_kbps = int(stream.get('bit_rate', 0)) / 1000
                        else:
                            # Estimate video bitrate by subtracting audio bitrates from total
                            total_bitrate = int(format_info.get('bit_rate', 0)) / 1000
                            audio_bitrate = sum(int(s.get('bit_rate', 0)) / 1000
                                                for s in streams
                                                if s.get('codec_type') == 'audio')
                            bitrate_kbps = total_bitrate - audio_bitrate

                        if bitrate_kbps > 0:
                            formatted += f"  Bitrate: {bitrate_kbps:.2f} kbps\n"
                        formatted += "\n"

                        # Add quality analysis in a separate section
                        if bitrate_kbps > 0:
                            formatted += "  📊 QUALITY ANALYSIS\n"
                            formatted += "  " + "-" * 30 + "\n"
                            quality_analysis = self.analyze_video_quality(resolution, bitrate_kbps, codec_name,
                                                                          framerate)
                            if quality_analysis:
                                formatted += f"  {quality_analysis}\n"
                            formatted += "\n"

            # Audio streams
            audio_streams = [s for s in streams if s.get('codec_type') == 'audio']
            if audio_streams:
                formatted += "🔊 AUDIO STREAMS\n"
                formatted += "=" * 50 + "\n"
                for i, stream in enumerate(audio_streams, 1):
                    formatted += f"Audio Stream #{i}\n"
                    formatted += f"  Codec: {stream.get('codec_name', 'N/A')}\n"
                    formatted += f"  Channels: {stream.get('channels', 'N/A')}\n"
                    formatted += f"  Sample Rate: {stream.get('sample_rate', 'N/A')} Hz\n"
                    if stream.get('bit_rate'):
                        formatted += f"  Bitrate: {int(stream.get('bit_rate', 0)) / 1000:.2f} kbps\n"
                    formatted += "\n"

            # Subtitle streams
            subtitle_streams = [s for s in streams if s.get('codec_type') == 'subtitle']
            if subtitle_streams:
                formatted += "💬 SUBTITLE STREAMS\n"
                formatted += "=" * 50 + "\n"
                for i, stream in enumerate(subtitle_streams, 1):
                    formatted += f"Subtitle Stream #{i}\n"
                    formatted += f"  Codec: {stream.get('codec_name', 'N/A')}\n"
                    formatted += f"  Language: {stream.get('tags', {}).get('language', 'N/A')}\n"
                    formatted += "\n"

            # Separate raw metadata
            raw_json = json.dumps(metadata, indent=2)
            self.raw_metadata_box.setText(raw_json)

            return formatted
        except Exception as e:
            return f"Error formatting metadata: {str(e)}"

    def get_video_metadata(self, file_path):
        if not self.check_ffmpeg():
            return "Error: FFmpeg/FFprobe not found. Please install FFmpeg."

        try:
            command = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]

            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')

            if result.returncode != 0:
                return f"Error: Unable to read metadata from {file_path}"

            metadata = json.loads(result.stdout)
            return self.format_metadata(metadata)

        except Exception as e:
            return f"Error: {str(e)}"

    def display_metadata(self, file_path):
        # Store current file path
        self.current_file = file_path

        # Display basic metadata first
        metadata = self.get_video_metadata(file_path)
        self.metadata_display.setText(metadata)
        self.metadata_display.verticalScrollBar().setValue(0)
        self.generate_thumbnail(file_path)

        # Start LUFS analysis after a short delay (500ms)
        self.lufs_timer.start(500)

    def process_lufs_analysis(self):
        if not self.current_file:
            return

        # Get current text
        current_text = self.metadata_display.toPlainText()

        # Find audio streams section and add LUFS analysis
        if "🔊 AUDIO STREAMS" in current_text:
            lufs_analysis = self.audio_analyzer.get_lufs(self.current_file)
            if lufs_analysis:

                # Split text at audio streams
                parts = current_text.split("🔊 AUDIO STREAMS")
                audio_section = parts[1].split("=", 1)[1]  # Get after the === line

                # Split audio section into streams
                stream_parts = audio_section.split("Audio Stream #")

                # Process each stream
                processed_streams = ["Audio Stream #" + part if i > 0 else part
                                     for i, part in enumerate(stream_parts)]

                # Add LUFS analysis to the first audio stream
                if len(processed_streams) > 1:
                    stream_text = processed_streams[1]
                    if not "LOUDNESS ANALYSIS" in stream_text:
                        analysis_text = "\n  " + "-" * 30 + "\n"
                        analysis_text += "  " + lufs_analysis.replace("\n", "\n  ") + "\n\n"
                        processed_streams[1] = stream_text.rstrip() + analysis_text

                # Reconstruct the text
                new_audio_section = "".join(processed_streams)
                new_text = parts[0] + "🔊 AUDIO STREAMS\n" + new_audio_section

                if len(parts) > 2:
                    new_text += "".join(parts[2:])

                # Update the display
                self.metadata_display.setText(new_text)
                self.metadata_display.verticalScrollBar().setValue(0)

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Media File",
            "",
            "Media Files (*.mp4 *.avi *.mkv *.mov *.wmv *.webm *.gif *.webp"
            " *.mp3 *.wav *.flac *.m4a *.aac);;All Files (*.*)"
        )
        if file_path:
            self.display_metadata(file_path)

    # Add drag and drop support for the main window
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            self.display_metadata(files[0])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = VideoMetadataViewer()
    viewer.show()
    sys.exit(app.exec_())
