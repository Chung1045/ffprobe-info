import os
import sys

from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import QApplication

from viewer import ffmpeg_tools
from viewer.resources import resource_path
from viewer.ui.dialogs import show_ffmpeg_error
from viewer.ui.main_window import MetadataWindow
from viewer.ui.styles import app_stylesheet


def load_font() -> str:
    font_id = QFontDatabase.addApplicationFont(str(resource_path("res/font", "FiraCode-Regular.ttf")))
    if font_id != -1:
        return QFontDatabase.applicationFontFamilies(font_id)[0]
    print("Could not load FiraCode; using monospace.")
    return "monospace"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Media Metadata Viewer")
    app.setStyleSheet(app_stylesheet(load_font()))

    if not ffmpeg_tools.ffmpeg_available():
        show_ffmpeg_error()
        return 1

    window = MetadataWindow()
    window.show()

    # Lets you "Open with" / drop a file on the exe: MediaMetadataViewer.exe clip.mp4
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        window.load_file(sys.argv[1])

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
