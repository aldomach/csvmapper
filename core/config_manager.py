"""core/config_manager.py — Persistencia de sesión y preferencias."""
import json
from pathlib import Path
from PySide6.QtCore import QSettings


class ConfigManager:
    def __init__(self):
        self.settings = QSettings("CSVMapper", "CSVMapper")

    def save_session(self, work_files: list, ref_files: list):
        self.settings.setValue("session/work_files", json.dumps(work_files))
        self.settings.setValue("session/ref_files",  json.dumps(ref_files))
        self.settings.sync()

    def load_session(self) -> tuple:
        try:
            work = json.loads(self.settings.value("session/work_files", "[]"))
            ref  = json.loads(self.settings.value("session/ref_files",  "[]"))
            return ([f for f in work if Path(f).exists()],
                    [f for f in ref  if Path(f).exists()])
        except Exception:
            return [], []

    def save_last_dir(self, directory: str):
        self.settings.setValue("paths/last_dir", directory)

    def load_last_dir(self) -> str:
        return self.settings.value("paths/last_dir", "")

    def save_geometry(self, geometry_bytes):
        self.settings.setValue("window/geometry", geometry_bytes)

    def load_geometry(self):
        return self.settings.value("window/geometry")

    def save_theme(self, theme: str):
        self.settings.setValue("ui/theme", theme)
        self.settings.sync()

    def load_theme(self) -> str:
        return self.settings.value("ui/theme", "light")
