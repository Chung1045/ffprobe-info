import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QMessageBox, QPushButton, QTextEdit, QVBoxLayout

class LUFSResultDialog(QDialog):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LUFS Analysis Results")
        self.setMinimumWidth(400)

        view = QTextEdit()
        view.setReadOnly(True)
        view.setPlainText(text)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(view)
        layout.addWidget(close, alignment=Qt.AlignCenter)


_INSTALL_HELP = {
    "darwin": "Using Homebrew:\n1. Install Homebrew from https://brew.sh\n2. Run: brew install ffmpeg",
    "win32": ("1. Download FFmpeg from https://ffmpeg.org/download.html\n"
              "2. Extract the archive\n3. Add FFmpeg's bin folder to your system's PATH"),
    "linux": ("Using apt (Ubuntu/Debian):\nsudo apt update && sudo apt install ffmpeg\n\n"
              "Using dnf (Fedora):\nsudo dnf install ffmpeg"),
}


def show_ffmpeg_error(parent=None):
    help_text = _INSTALL_HELP.get(sys.platform, _INSTALL_HELP["linux"])
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Critical)
    box.setWindowTitle("FFmpeg Not Found")
    box.setText("FFmpeg is required but not found on your system.\n\nPlease install FFmpeg:\n\n" + help_text)
    box.exec_()
