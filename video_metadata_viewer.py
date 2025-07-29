import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QPixmap, QFontDatabase, QFont
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout,
                             QTextEdit, QWidget, QFileDialog, QLabel, QHBoxLayout,
                             QMessageBox, QDialog, QTabWidget)

from audio_analyzer import AudioAnalyzer
from video_quality_analyzer import VideoQualityAnalyzer


class LUFSWorker(QObject):
    """Worker to perform LUFS analysis in background thread"""
    finished = pyqtSignal(str)

    def __init__(self, file_path, audio_analyzer):
        super().__init__()
        self.file_path = file_path
        self.audio_analyzer = audio_analyzer

    def run(self):
        result = self.audio_analyzer.get_lufs(self.file_path)
        self.finished.emit(result)


class LUFSResultDialog(QDialog):
    def __init__(self, lufs_analysis, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LUFS Analysis Results")
        self.setMinimumWidth(400)

        # Get the custom font family from parent
        if parent and hasattr(parent, 'custom_font_family'):
            self.custom_font_family = parent.custom_font_family
        else:
            self.custom_font_family = "monospace"

        layout = QVBoxLayout(self)

        # Create text display
        text_display = QTextEdit()
        text_display.setReadOnly(True)
        text_display.setText(lufs_analysis)
        text_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #dcdcdc;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-family: '{self.custom_font_family}', monospace;
                font-size: 12px;
            }}
        """)
        layout.addWidget(text_display)

        # Add close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #3b3b3b;
                border: none;
                border-radius: 5px;
                padding: 8px;
                color: #dcdcdc;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #4b4b4b;
            }
        """)
        layout.addWidget(close_button, alignment=Qt.AlignCenter)

        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #dcdcdc;
            }
        """)


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
        self.content.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #dcdcdc;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-family: monospace;
                font-size: 12px;
            }
        """)
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
        self.setFixedHeight(100)
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
        self.setAcceptDrops(True)
        self.min_width_for_horizontal = 1000

        # Load custom font
        self.load_custom_font()

        self.setup_ui()
        self.current_thumbnail = None
        self.quality_analyzer = VideoQualityAnalyzer()
        self.audio_analyzer = AudioAnalyzer()
        self.current_file = None  # To store current file path
        self.lufs_progress = None  # For progress dialog

    def load_custom_font(self):
        """Load the custom FiraCode font from file"""
        # Get the directory where the script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(script_dir, "FiraCode-Regular.ttf")

        # Load the font
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            self.custom_font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
        else:
            print("Error: Could not load custom font. Using fallback fonts.")
            self.custom_font_family = "monospace"

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
                font-family: '{self.custom_font_family}', monospace;
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
            "• Click the 'Analyze LUFS' button after loading a file to perform loudness analysis"
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
        self.thumbnail_label.setMinimumSize(150, 150)
        self.thumbnail_label.setMaximumSize(200, 200)
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
        self.file_name_label.setMinimumWidth(150)
        self.file_name_label.setMaximumWidth(200)
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

        # Buttons container widget
        self.buttons_widget = QWidget()
        self.buttons_widget.setFixedWidth(200)  # Match thumbnail width
        self.buttons_layout = QVBoxLayout(self.buttons_widget)
        self.buttons_layout.setAlignment(Qt.AlignHCenter)
        self.buttons_layout.setSpacing(10)  # Add some space between buttons
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)

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
        self.buttons_layout.addWidget(self.select_button, 0, Qt.AlignHCenter)

        self.lufs_button_container = QWidget()
        self.lufs_button_container.setFixedWidth(150)
        lufs_button_layout = QHBoxLayout(self.lufs_button_container)
        lufs_button_layout.setContentsMargins(0, 0, 0, 0)
        lufs_button_layout.setSpacing(5)
        lufs_button_layout.setAlignment(Qt.AlignCenter)

        self.lufs_button = QPushButton("Analyze LUFS")
        self.lufs_button.setFixedWidth(120)
        self.lufs_button.setEnabled(False)  # Initially disabled
        self.lufs_button.setStyleSheet("""
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
            QPushButton:disabled {
                background-color: #2b2b2b;
                color: #666666;
            }
        """)
        self.lufs_button.clicked.connect(self.process_lufs_analysis)

        lufs_button_layout.addWidget(self.lufs_button)

        self.buttons_layout.addWidget(self.lufs_button_container, 0, Qt.AlignHCenter)

        # Add buttons container to right panel
        self.right_layout.addWidget(self.buttons_widget)

        # Left panel for info
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)

        # Create tab widget for metadata display
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: #1e1e1e;
                border-radius: 5px;
            }}
            QTabBar::tab {{
                background-color: #2b2b2b;
                color: #a0a0a0;
                padding: 8px 12px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }}
            QTabBar::tab:selected {{
                background-color: #1e1e1e;
                color: #ffffff;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: #3b3b3b;
            }}
        """)

        # Create tabs for different metadata categories
        # Overview tab
        self.overview_tab = QWidget()
        overview_layout = QVBoxLayout(self.overview_tab)
        self.overview_display = QTextEdit()
        self.overview_display.setReadOnly(True)
        self.overview_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #dcdcdc;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-family: '{self.custom_font_family}', monospace;
                font-size: 12px;
            }}
        """)
        overview_layout.addWidget(self.overview_display)
        self.tab_widget.addTab(self.overview_tab, "📁 Overview")

        # Video tab
        self.video_tab = QWidget()
        video_layout = QVBoxLayout(self.video_tab)
        self.video_display = QTextEdit()
        self.video_display.setReadOnly(True)
        self.video_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #dcdcdc;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-family: '{self.custom_font_family}', monospace;
                font-size: 12px;
            }}
        """)
        video_layout.addWidget(self.video_display)
        self.tab_widget.addTab(self.video_tab, "🎥 Video")

        # Audio tab
        self.audio_tab = QWidget()
        audio_layout = QVBoxLayout(self.audio_tab)
        self.audio_display = QTextEdit()
        self.audio_display.setReadOnly(True)
        self.audio_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #dcdcdc;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-family: '{self.custom_font_family}', monospace;
                font-size: 12px;
            }}
        """)
        audio_layout.addWidget(self.audio_display)
        self.tab_widget.addTab(self.audio_tab, "🔊 Audio")

        # Subtitles tab
        self.subtitles_tab = QWidget()
        subtitles_layout = QVBoxLayout(self.subtitles_tab)
        self.subtitles_display = QTextEdit()
        self.subtitles_display.setReadOnly(True)
        self.subtitles_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #dcdcdc;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-family: '{self.custom_font_family}', monospace;
                font-size: 12px;
            }}
        """)
        subtitles_layout.addWidget(self.subtitles_display)
        self.tab_widget.addTab(self.subtitles_tab, "💬 Subtitles")

        # Raw metadata tab
        self.raw_tab = QWidget()
        raw_layout = QVBoxLayout(self.raw_tab)
        self.raw_display = QTextEdit()
        self.raw_display.setReadOnly(True)
        self.raw_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #dcdcdc;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-family: '{self.custom_font_family}', monospace;
                font-size: 12px;
            }}
        """)
        raw_layout.addWidget(self.raw_display)
        self.tab_widget.addTab(self.raw_tab, "🔧 Raw Metadata")

        self.left_layout.addWidget(self.tab_widget)

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
                    '-vframes', '1', '-vf', 'scale=-1:150',
                    thumb_path
                ]
                process = subprocess.run(video_command, capture_output=True, encoding='utf-8')

            if process.returncode == 0 and os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
                pixmap = QPixmap(thumb_path)

                # Handle different aspect ratios
                if self.get_file_type(self.get_metadata(file_path)) == 'audio':
                    size = min(200, max(150, min(pixmap.width(), pixmap.height())))
                    scaled_pixmap = pixmap.scaled(
                        size, size,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                else:
                    if pixmap.width() > pixmap.height():
                        scaled_pixmap = pixmap.scaledToWidth(200, Qt.SmoothTransformation)
                    else:
                        scaled_pixmap = pixmap.scaledToHeight(150, Qt.SmoothTransformation)

                self.thumbnail_label.setPixmap(scaled_pixmap)
                filename = os.path.basename(file_path)

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

                    max_filename_length = 30
                    if len(filename) > max_filename_length:
                        displayed_filename = filename[:max_filename_length - 3] + "..."
                    else:
                        displayed_filename = filename

                    if title and title != filename:
                        displayed_title = title
                        self.file_name_label.setText(f"{displayed_title}\n({displayed_filename})")
                    else:
                        self.file_name_label.setText(displayed_filename)

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
            print(f"get_metadata: {result.stdout}")
            return json.loads(result.stdout)
        return {}

    def analyze_video_quality(self, resolution, bitrate_kbps, codec_name, framerate):
        """Analyze if video bitrate is sufficient for the resolution"""
        return self.quality_analyzer.analyze_video_quality(resolution, bitrate_kbps, codec_name, framerate)

    def get_file_type(self, metadata):
        """Determine if the file is video or audio"""
        streams = metadata.get('streams', [])
        video_codecs = {'h264', 'hevc', 'vp8', 'vp9', 'av1'}
        has_video = any(s.get('codec_type') == 'video' and
                        s.get('codec_name', '').lower() in video_codecs
                        for s in streams)
        print("Get file type")
        print("File type is: ", 'video' if has_video else 'audio')
        return 'video' if has_video else 'audio'

    def format_metadata_by_category(self, metadata):
        """Format metadata into different categories for different tabs"""
        try:
            format_info = metadata.get('format', {})
            streams = metadata.get('streams', [])
            file_type = self.get_file_type(metadata)

            separator_length = 50
            separator = "=" * separator_length + "\n"

            # Overview information
            overview = "📁 FILE INFORMATION\n"
            overview += separator
            overview += f"Type: {'Video' if file_type == 'video' else 'Audio'} File\n"
            overview += f"Filename: {format_info.get('filename', 'N/A')}\n"
            overview += f"Format: {format_info.get('format_name', 'N/A')}\n"
            overview += f"Duration: {float(format_info.get('duration', 0)):.2f} seconds\n"
            overview += f"Size: {int(format_info.get('size', 0)) / (1024 * 1024):.2f} MB\n"
            overview += f"Bitrate: {int(format_info.get('bit_rate', 0)) / 1000:.2f} kbps\n"

            tags = format_info.get('tags', {})
            if tags:
                overview += "\n📌 TAGS\n"
                overview += separator
                for key, value in tags.items():
                    overview += f"{key.title()}: {value}\n"
            overview += "\n"

            # Video streams information
            video_info = ""
            video_streams = [s for s in streams if s.get('codec_type') == 'video'
                             and s.get('codec_name', '').lower() != 'mjpeg']
            if video_streams:
                video_info += "🎥 VIDEO STREAMS\n"
                video_info += separator
                for i, stream in enumerate(video_streams, 1):
                    video_info += f"Video Stream #{i}\n"
                    codec_name = stream.get('codec_name', 'N/A').lower()
                    video_info += f"  Codec: {codec_name.upper()}\n"

                    resolution = f"{stream.get('width', 'N/A')}x{stream.get('height', 'N/A')}"
                    video_info += f"  Resolution: {resolution}\n"

                    framerate = stream.get('r_frame_rate', '30/1')
                    video_info += f"  Framerate: {framerate}\n"
                    video_info += f"  Pixel Format: {stream.get('pix_fmt', 'N/A')}\n"

                    if stream.get('bit_rate'):
                        bitrate_kbps = int(stream.get('bit_rate', 0)) / 1000
                    else:
                        total_bitrate = int(format_info.get('bit_rate', 0)) / 1000
                        audio_bitrate = sum(int(s.get('bit_rate', 0)) / 1000
                                            for s in streams
                                            if s.get('codec_type') == 'audio')
                        bitrate_kbps = total_bitrate - audio_bitrate

                    if bitrate_kbps > 0:
                        video_info += f"  Bitrate: {bitrate_kbps:.2f} kbps\n"
                    video_info += "\n"

                    if bitrate_kbps > 0:
                        video_info += "  📊 QUALITY ANALYSIS\n"
                        video_info += "  " + "-" * 30 + "\n"
                        quality_analysis = self.analyze_video_quality(resolution, bitrate_kbps, codec_name,
                                                                      framerate)
                        if quality_analysis:
                            video_info += f"  {quality_analysis}\n"
                        video_info += "\n"

            # Audio streams information
            audio_info = ""
            audio_streams = [s for s in streams if s.get('codec_type') == 'audio']
            if audio_streams:
                audio_info += "🔊 AUDIO STREAMS\n"
                audio_info += separator
                for i, stream in enumerate(audio_streams, 1):
                    audio_info += f"Audio Stream #{i}\n"
                    audio_info += f"  Codec: {stream.get('codec_name', 'N/A')}\n"
                    audio_info += f"  Channels: {stream.get('channels', 'N/A')}\n"
                    audio_info += f"  Sample Rate: {stream.get('sample_rate', 'N/A')} Hz\n"
                    if stream.get('bit_rate'):
                        audio_info += f"  Bitrate: {int(stream.get('bit_rate', 0)) / 1000:.2f} kbps\n"
                    audio_info += "\n"

            # Subtitle streams information
            subtitle_info = ""
            subtitle_streams = [s for s in streams if s.get('codec_type') == 'subtitle']
            if subtitle_streams:
                subtitle_info += "💬 SUBTITLE STREAMS\n"
                subtitle_info += separator
                for i, stream in enumerate(subtitle_streams, 1):
                    subtitle_info += f"Subtitle Stream #{i}\n"
                    subtitle_info += f"  Codec: {stream.get('codec_name', 'N/A')}\n"
                    subtitle_info += f"  Language: {stream.get('tags', {}).get('language', 'N/A')}\n"
                    subtitle_info += "\n"
            else:
                subtitle_info = "No subtitle streams found."

            # Raw metadata
            raw_json = json.dumps(metadata, indent=2)

            return {
                'overview': overview,
                'video': video_info if video_info else "No video streams found.",
                'audio': audio_info if audio_info else "No audio streams found.",
                'subtitles': subtitle_info,
                'raw': raw_json
            }

        except Exception as e:
            error_msg = f"Error formatting metadata: {str(e)}"
            return {
                'overview': error_msg,
                'video': error_msg,
                'audio': error_msg,
                'subtitles': error_msg,
                'raw': error_msg
            }

    def format_metadata(self, metadata):
        try:
            format_info = metadata.get('format', {})
            streams = metadata.get('streams', [])
            file_type = self.get_file_type(metadata)

            separator_length = 50
            separator = "=" * separator_length + "\n"

            formatted = "📁 FILE INFORMATION\n"
            formatted += separator
            formatted += f"Type: {'Video' if file_type == 'video' else 'Audio'} File\n"
            formatted += f"Filename: {format_info.get('filename', 'N/A')}\n"
            formatted += f"Format: {format_info.get('format_name', 'N/A')}\n"
            formatted += f"Duration: {float(format_info.get('duration', 0)):.2f} seconds\n"
            formatted += f"Size: {int(format_info.get('size', 0)) / (1024 * 1024):.2f} MB\n"
            formatted += f"Bitrate: {int(format_info.get('bit_rate', 0)) / 1000:.2f} kbps\n"

            tags = format_info.get('tags', {})
            if tags:
                formatted += "\n📌 TAGS\n"
                formatted += separator
                for key, value in tags.items():
                    formatted += f"{key.title()}: {value}\n"
            formatted += "\n"

            if file_type == 'video':
                video_streams = [s for s in streams if s.get('codec_type') == 'video'
                                 and s.get('codec_name', '').lower() != 'mjpeg']
                if video_streams:
                    formatted += "🎥 VIDEO STREAMS\n"
                    formatted += separator
                    for i, stream in enumerate(video_streams, 1):
                        formatted += f"Video Stream #{i}\n"
                        codec_name = stream.get('codec_name', 'N/A').lower()
                        formatted += f"  Codec: {codec_name.upper()}\n"

                        resolution = f"{stream.get('width', 'N/A')}x{stream.get('height', 'N/A')}"
                        formatted += f"  Resolution: {resolution}\n"

                        framerate = stream.get('r_frame_rate', '30/1')
                        formatted += f"  Framerate: {framerate}\n"
                        formatted += f"  Pixel Format: {stream.get('pix_fmt', 'N/A')}\n"

                        if stream.get('bit_rate'):
                            bitrate_kbps = int(stream.get('bit_rate', 0)) / 1000
                        else:
                            total_bitrate = int(format_info.get('bit_rate', 0)) / 1000
                            audio_bitrate = sum(int(s.get('bit_rate', 0)) / 1000
                                                for s in streams
                                                if s.get('codec_type') == 'audio')
                            bitrate_kbps = total_bitrate - audio_bitrate

                        if bitrate_kbps > 0:
                            formatted += f"  Bitrate: {bitrate_kbps:.2f} kbps\n"
                        formatted += "\n"

                        if bitrate_kbps > 0:
                            formatted += "  📊 QUALITY ANALYSIS\n"
                            formatted += "  " + "-" * 30 + "\n"
                            quality_analysis = self.analyze_video_quality(resolution, bitrate_kbps, codec_name,
                                                                          framerate)
                            if quality_analysis:
                                formatted += f"  {quality_analysis}\n"
                            formatted += "\n"

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

            subtitle_streams = [s for s in streams if s.get('codec_type') == 'subtitle']
            if subtitle_streams:
                formatted += "💬 SUBTITLE STREAMS\n"
                formatted += "=" * 50 + "\n"
                for i, stream in enumerate(subtitle_streams, 1):
                    formatted += f"Subtitle Stream #{i}\n"
                    formatted += f"  Codec: {stream.get('codec_name', 'N/A')}\n"
                    formatted += f"  Language: {stream.get('tags', {}).get('language', 'N/A')}\n"
                    formatted += "\n"

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
            print("Video Metadata:", metadata)
            return self.format_metadata(metadata)

        except Exception as e:
            return f"Error: {str(e)}"

    def display_metadata(self, file_path):
        """Display metadata in the tabbed interface"""
        self.current_file = file_path

        # Get metadata
        if not self.check_ffmpeg():
            error_msg = "Error: FFmpeg/FFprobe not found. Please install FFmpeg."
            self.overview_display.setText(error_msg)
            self.video_display.setText(error_msg)
            self.audio_display.setText(error_msg)
            self.subtitles_display.setText(error_msg)
            self.raw_display.setText(error_msg)
            return

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
                error_msg = f"Error: Unable to read metadata from {file_path}"
                self.overview_display.setText(error_msg)
                self.video_display.setText(error_msg)
                self.audio_display.setText(error_msg)
                self.subtitles_display.setText(error_msg)
                self.raw_display.setText(error_msg)
                return

            metadata = json.loads(result.stdout)

            # Format metadata for different tabs
            formatted_data = self.format_metadata_by_category(metadata)

            # Update each tab with formatted data
            self.overview_display.setText(formatted_data['overview'])
            self.video_display.setText(formatted_data['video'])
            self.audio_display.setText(formatted_data['audio'])
            self.subtitles_display.setText(formatted_data['subtitles'])
            self.raw_display.setText(formatted_data['raw'])

            # Reset scroll position for all tabs
            self.overview_display.verticalScrollBar().setValue(0)
            self.video_display.verticalScrollBar().setValue(0)
            self.audio_display.verticalScrollBar().setValue(0)
            self.subtitles_display.verticalScrollBar().setValue(0)
            self.raw_display.verticalScrollBar().setValue(0)

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.overview_display.setText(error_msg)
            self.video_display.setText(error_msg)
            self.audio_display.setText(error_msg)
            self.subtitles_display.setText(error_msg)
            self.raw_display.setText(error_msg)

        # Generate thumbnail
        self.generate_thumbnail(file_path)

        # Enable LUFS button when file is loaded
        self.lufs_button.setEnabled(True)

    def process_lufs_analysis(self):
        """Start LUFS analysis in a background thread"""
        if not self.current_file:
            return

        # Disable LUFS button during analysis
        self.lufs_button.setEnabled(False)
        self.lufs_button.setText("Analyzing...")

        # Create worker and thread
        self.lufs_worker = LUFSWorker(self.current_file, self.audio_analyzer)
        self.lufs_thread = threading.Thread(target=self.lufs_worker.run)

        # Connect finished signal
        self.lufs_worker.finished.connect(self.update_lufs_results)

        # Start the analysis thread
        self.lufs_thread.daemon = True
        self.lufs_thread.start()

    def update_lufs_results(self, lufs_analysis):
        """Update UI with LUFS analysis results"""

        # Reset button state
        self.lufs_button.setEnabled(True)
        self.lufs_button.setText("Analyze LUFS")

        # Show results in popup dialog
        dialog = LUFSResultDialog(lufs_analysis, self)
        dialog.exec_()

        # Update the audio tab with LUFS analysis
        current_text = self.audio_display.toPlainText()

        if "🔊 AUDIO STREAMS" in current_text and lufs_analysis:
            parts = current_text.split("Audio Stream #")
            if len(parts) > 1:
                # Add LUFS analysis to the first audio stream
                stream_text = parts[1]
                if "LOUDNESS ANALYSIS" not in stream_text:
                    # Find the end of the first stream info
                    lines = stream_text.split('\n')
                    insert_index = 0
                    for i, line in enumerate(lines):
                        if line.strip() == "" and i > 0:  # First empty line after stream info
                            insert_index = i
                            break

                    if insert_index == 0:
                        insert_index = len(lines)

                    # Insert LUFS analysis
                    analysis_lines = [
                        "",
                        "  📊 LOUDNESS ANALYSIS",
                        "  " + "-" * 30
                    ]
                    for line in lufs_analysis.split('\n'):
                        if line.strip():
                            analysis_lines.append(f"  {line}")
                    analysis_lines.append("")

                    # Insert the analysis
                    lines[insert_index:insert_index] = analysis_lines
                    parts[1] = '\n'.join(lines)

                    new_text = "Audio Stream #".join(parts)
                    self.audio_display.setText(new_text)
                    self.audio_display.verticalScrollBar().setValue(0)

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Media File",
            "",
            "Media Files (*.mp4 *.avi *.mkv *.mov *.wmv *.webm *.gif *.webp"
            " *.mp3 *.wav *.flac *.m4a *.aac *hevc *heic *png *jpg);;All Files (*.*)"
        )
        if file_path:
            print("The media file path is: " + file_path)
            # Fix: Call display_metadata instead of just setting the label
            self.display_metadata(file_path)

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