import threading

from PyQt5.QtCore import QObject, pyqtSignal


class LoudnessJob(QObject):
    """Runs the (slow) loudness analysis off the UI thread and reports back via a signal."""
    done = pyqtSignal(str, str)  # (file_path, result_text)

    def start(self, analyzer, file_path: str):
        def work():
            self.done.emit(file_path, analyzer.get_lufs(file_path))
        threading.Thread(target=work, daemon=True).start()
