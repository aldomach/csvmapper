"""
config_manager.py - Persists open files and app settings using QSettings
"""
import json
from pathlib import Path
from PySide6.QtCore import QSettings


class ConfigManager:
    def __init__(self):
        self.settings = QSettings("CSVMapper", "CSVMapper")

    # ── Session files ──────────────────────────────────────────────────────────

    def save_session(self, work_files: list[str], ref_files: list[str]):
        """Persist the list of open files for each tab."""
        self.settings.setValue("session/work_files", json.dumps(work_files))
        self.settings.setValue("session/ref_files",  json.dumps(ref_files))
        self.settings.sync()

    def load_session(self) -> tuple[list[str], list[str]]:
        """Return (work_files, ref_files) from last session."""
        try:
            work = json.loads(self.settings.value("session/work_files", "[]"))
            ref  = json.loads(self.settings.value("session/ref_files",  "[]"))
            # Filter out files that no longer exist on disk
            work = [f for f in work if Path(f).exists()]
            ref  = [f for f in ref  if Path(f).exists()]
            return work, ref
        except Exception:
            return [], []

    # ── Recent paths ───────────────────────────────────────────────────────────

    def save_last_dir(self, directory: str):
        self.settings.setValue("paths/last_dir", directory)

    def load_last_dir(self) -> str:
        return self.settings.value("paths/last_dir", "")

    # ── Geometry ───────────────────────────────────────────────────────────────

    def save_geometry(self, geometry_bytes):
        self.settings.setValue("window/geometry", geometry_bytes)

    def load_geometry(self):
        return self.settings.value("window/geometry")

    def save_state(self, state_bytes):
        self.settings.setValue("window/state", state_bytes)

    def load_state(self):
        return self.settings.value("window/state")

    # ── Per-file column mapping ────────────────────────────────────────────────

    def save_column_mapping(self, filepath: str, mapping: dict):
        """Save which column is the 'match' column for a given work file."""
        key = f"mapping/{Path(filepath).name}"
        self.settings.setValue(key, json.dumps(mapping))

    def load_column_mapping(self, filepath: str) -> dict:
        key = f"mapping/{Path(filepath).name}"
        try:
            return json.loads(self.settings.value(key, "{}"))
        except Exception:
            return {}
