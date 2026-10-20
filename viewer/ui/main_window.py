import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QBoxLayout, QFileDialog, QLabel, QMainWindow, QVBoxLayout, QWidget

from .. import ffmpeg_tools, formatting
from ..analyzers import AudioAnalyzer
from .dialogs import LUFSResultDialog
from .widgets import MetadataTabs, SidePanel
from .workers import LoudnessJob

TIPS = (
    "💡 Tips:\n"
    "• Drag and drop any media file anywhere on this window\n"
    "• Or click the 'Select Media File' button\n"
    "• Supports video (mp4, avi, mkv, etc.) and audio (mp3, wav, m4a, etc.)\n"
    "• Click the 'Analyze LUFS' button after loading a file to perform loudness analysis"
)
FILE_FILTER = ("Media Files (*.mp4 *.avi *.mkv *.mov *.wmv *.webm *.gif *.webp "
               "*.mp3 *.wav *.flac *.m4a *.aac *.hevc *.heic *.png *.jpg);;All Files (*.*)")
NARROW_BREAKPOINT = 1000
QWIDGETSIZE_MAX = 16777215


class MetadataWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Media Metadata Viewer")
        self.resize(1200, 800)
        self.setAcceptDrops(True)

        self.audio_analyzer = AudioAnalyzer()
        self.loudness_job = LoudnessJob()
        self.loudness_job.done.connect(self._on_loudness_done)

        self.current_file = None
        self.metadata = None
        self._narrow = None  # unknown until first layout pass

        self._build_ui()

    # ---------- construction ----------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(20)

        tips = QLabel(TIPS)
        tips.setObjectName("tips")
        tips.setWordWrap(True)
        outer.addWidget(tips)

        self.tabs = MetadataTabs()
        self.side_panel = SidePanel()
        self.side_panel.select_clicked.connect(self.select_file)
        self.side_panel.lufs_clicked.connect(self.start_loudness_analysis)

        self.content_layout = QBoxLayout(QBoxLayout.LeftToRight)
        self.content_layout.setSpacing(20)
        self.content_layout.addWidget(self.tabs, 1)
        self.content_layout.addWidget(self.side_panel)
        outer.addLayout(self.content_layout)

        self._update_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_layout()

    def _update_layout(self):
        """Side panel sits on the right in wide windows and above the tabs in narrow ones."""
        narrow = self.width() < NARROW_BREAKPOINT
        if narrow == self._narrow:
            return
        self._narrow = narrow
        self.content_layout.removeWidget(self.side_panel)
        if narrow:
            self.content_layout.setDirection(QBoxLayout.TopToBottom)
            self.content_layout.insertWidget(0, self.side_panel)
            self.side_panel.setMaximumWidth(QWIDGETSIZE_MAX)
        else:
            self.content_layout.setDirection(QBoxLayout.LeftToRight)
            self.content_layout.addWidget(self.side_panel)
            self.side_panel.setMaximumWidth(250)

    # ---------- loading a file ----------
    def load_file(self, path: str):
        self.current_file = path
        self.metadata = None
        try:
            metadata = ffmpeg_tools.probe(path)
        except (ffmpeg_tools.FFmpegError, ValueError) as e:  # ValueError: bad JSON from ffprobe
            self.tabs.show_error(f"Error: {e}")
            self.side_panel.set_lufs_state(False)
            return

        self.metadata = metadata
        self.tabs.set_texts(formatting.format_all(metadata))
        self._show_thumbnail(path, metadata)
        self.side_panel.set_lufs_state(True)

    def _show_thumbnail(self, path: str, metadata: dict):
        filename = os.path.basename(path)
        tags = {k.lower(): v for k, v in metadata.get("format", {}).get("tags", {}).items()}
        title = tags.get("title", "")
        short = filename if len(filename) <= 30 else filename[:27] + "..."
        if title and title != filename:
            self.side_panel.set_filename(f"{title}\n({short})", f"{title}\n({filename})")
        else:
            self.side_panel.set_filename(short, filename)

        pixmap = QPixmap()
        data = ffmpeg_tools.extract_thumbnail(path)
        if not (data and pixmap.loadFromData(data)):
            self.side_panel.set_thumbnail(None, "No thumbnail/album art")
            return

        if formatting.file_type(metadata) == "audio":
            size = min(200, max(150, min(pixmap.width(), pixmap.height())))
            pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        elif pixmap.width() > pixmap.height():
            pixmap = pixmap.scaledToWidth(200, Qt.SmoothTransformation)
        else:
            pixmap = pixmap.scaledToHeight(150, Qt.SmoothTransformation)
        self.side_panel.set_thumbnail(pixmap)

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Media File", "", FILE_FILTER)
        if path:
            self.load_file(path)

    def dragEnterEvent(self, event):
        event.accept() if event.mimeData().hasUrls() else event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            self.load_file(files[0])

    # ---------- loudness ----------
    def start_loudness_analysis(self):
        if not self.current_file:
            return
        self.side_panel.set_lufs_state(False, "Analyzing...")
        self.loudness_job.start(self.audio_analyzer, self.current_file)

    def _on_loudness_done(self, path: str, text: str):
        if path != self.current_file:  # user loaded another file while this was running
            return
        self.side_panel.set_lufs_state(True)
        if self.metadata:
            self.tabs.set_text("audio", formatting.format_audio(self.metadata, text))
        LUFSResultDialog(text, self).exec_()
