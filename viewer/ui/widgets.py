from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel, QPushButton, QTabWidget, QTextEdit, QVBoxLayout, QWidget


class MetadataTabs(QTabWidget):
    """The five read-only text tabs. Add a tab by adding one line to TABS."""
    TABS = [
        ("overview", "📁 Overview"),
        ("video", "🎥 Video"),
        ("audio", "🔊 Audio"),
        ("subtitles", "💬 Subtitles"),
        ("raw", "🔧 Raw Metadata"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.views = {}
        for key, title in self.TABS:
            view = QTextEdit()
            view.setReadOnly(True)
            self.addTab(view, title)
            self.views[key] = view

    def set_text(self, key: str, text: str):
        view = self.views[key]
        view.setPlainText(text)  # plain text: tags containing "<" must not be parsed as HTML
        view.verticalScrollBar().setValue(0)

    def set_texts(self, texts: dict):
        for key in self.views:
            self.set_text(key, texts.get(key, ""))

    def show_error(self, message: str):
        self.set_texts({key: message for key in self.views})


class SidePanel(QWidget):
    """Thumbnail, file name, and the two buttons."""
    select_clicked = pyqtSignal()
    lufs_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        layout.setSpacing(10)

        self.thumbnail = QLabel()
        self.thumbnail.setObjectName("thumbnail")
        self.thumbnail.setMinimumSize(150, 150)
        self.thumbnail.setMaximumSize(200, 200)
        self.thumbnail.setAlignment(Qt.AlignCenter)

        self.filename = QLabel()
        self.filename.setObjectName("filename")
        self.filename.setAlignment(Qt.AlignCenter)
        self.filename.setWordWrap(True)
        self.filename.setFixedWidth(200)

        self.select_button = QPushButton("Select Media File")
        self.lufs_button = QPushButton("Analyze LUFS")
        self.lufs_button.setEnabled(False)
        self.select_button.clicked.connect(self.select_clicked)
        self.lufs_button.clicked.connect(self.lufs_clicked)

        for widget in (self.thumbnail, self.filename, self.select_button, self.lufs_button):
            layout.addWidget(widget, 0, Qt.AlignHCenter)

    def set_thumbnail(self, pixmap: QPixmap = None, message: str = ""):
        if pixmap is None:
            self.thumbnail.clear()
            self.thumbnail.setText(message)
        else:
            self.thumbnail.setPixmap(pixmap)

    def set_filename(self, text: str, tooltip: str = ""):
        self.filename.setText(text)
        self.filename.setToolTip(tooltip or text)

    def set_lufs_state(self, enabled: bool, text: str = "Analyze LUFS"):
        self.lufs_button.setEnabled(enabled)
        self.lufs_button.setText(text)
