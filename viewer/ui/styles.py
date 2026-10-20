"""All QSS in one place. Applied once on the QApplication, so no per-widget stylesheets."""

BG, PANEL, BUTTON, BUTTON_HOVER = "#2b2b2b", "#1e1e1e", "#3b3b3b", "#4b4b4b"
TEXT, MUTED, DISABLED = "#dcdcdc", "#a0a0a0", "#666666"


def app_stylesheet(font_family: str) -> str:
    return f"""
        QMainWindow, QDialog, QWidget {{ background-color: {BG}; color: {TEXT}; }}

        QTextEdit {{
            background-color: {PANEL}; border: none; border-radius: 5px; padding: 10px;
            font-size: 12px; font-family: '{font_family}', monospace;
        }}

        QPushButton {{
            background-color: {BUTTON}; border: none; border-radius: 5px;
            padding: 8px; min-width: 80px;
        }}
        QPushButton:hover {{ background-color: {BUTTON_HOVER}; }}
        QPushButton:disabled {{ background-color: {BG}; color: {DISABLED}; }}

        QTabWidget::pane {{ border: none; background-color: {PANEL}; border-radius: 5px; }}
        QTabBar::tab {{
            background-color: {BG}; color: {MUTED}; padding: 8px 12px; margin-right: 2px;
            border-top-left-radius: 5px; border-top-right-radius: 5px;
        }}
        QTabBar::tab:selected {{ background-color: {PANEL}; color: #ffffff; }}
        QTabBar::tab:hover:!selected {{ background-color: {BUTTON}; }}

        QLabel#tips {{ color: {MUTED}; padding: 10px; background-color: {PANEL}; border-radius: 5px; }}
        QLabel#thumbnail {{ background-color: {PANEL}; border-radius: 5px; }}
        QLabel#filename {{ margin-bottom: 10px; padding: 5px; font-size: 11px; }}
    """
