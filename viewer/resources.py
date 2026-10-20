"""Locate bundled files both when running from source and when frozen by PyInstaller."""
import sys
from pathlib import Path

def resource_path(*parts: str) -> Path:
    # PyInstaller unpacks bundled data to sys._MEIPASS; from source we use the project root.
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base.joinpath(*parts)
