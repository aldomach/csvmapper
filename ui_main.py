"""
ui_main.py - MainWindow: pestañas, selector de tema claro/oscuro, sesión.
"""
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QLabel, QPushButton,
    QHBoxLayout, QWidget
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from config_manager import ConfigManager
from ref_tab import RefTab
from work_tab import WorkTab
from theme import THEMES


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CSVMapper")
        self.resize(1200, 750)
        self.setMinimumSize(800, 500)

        self.cfg = ConfigManager()
        self._theme = self.cfg.load_theme()   # "light" | "dark"
        self._build_ui()
        self._apply_theme()
        self._restore_session()

        self._save_timer = QTimer(self)
        self._save_timer.timeout.connect(self._save_session)
        self._save_timer.start(30_000)

    # ── Build UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Reference tab primero para que Work tab pueda consultarla
        self.ref_tab = RefTab(self.cfg, self._get_theme)
        self.ref_tab.ref_changed.connect(self._on_ref_changed)

        self.work_tab = WorkTab(self.cfg, self._get_ref, self._get_theme)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.work_tab, "📋  Trabajo")
        self.tabs.addTab(self.ref_tab, "📚  Referencia")

        # Toolbar superior con el botón de tema
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("btn_theme")
        self.btn_theme.setFixedSize(110, 30)
        self.btn_theme.clicked.connect(self._toggle_theme)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.btn_theme)

        # Contenedor central = toolbar + tabs
        central = QWidget()
        from PySide6.QtWidgets import QVBoxLayout
        vlay = QVBoxLayout(central)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)
        vlay.addWidget(toolbar_widget)
        vlay.addWidget(self.tabs)
        self.setCentralWidget(central)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self._ref_status = QLabel("Referencia: sin datos")
        self.status.addPermanentWidget(self._ref_status)
        self.status.showMessage("Listo")

    # ── Tema ───────────────────────────────────────────────────────────────────

    def _get_theme(self) -> str:
        return self._theme

    def _apply_theme(self):
        self.setStyleSheet(THEMES[self._theme])
        label = "🌙  Modo oscuro" if self._theme == "light" else "☀️  Modo claro"
        self.btn_theme.setText(label)
        # Notificar a los tabs para que actualicen colores internos
        if hasattr(self, "work_tab"):
            self.work_tab.refresh_theme()
        if hasattr(self, "ref_tab"):
            self.ref_tab.refresh_theme()

    def _toggle_theme(self):
        self._theme = "dark" if self._theme == "light" else "light"
        self.cfg.save_theme(self._theme)
        self._apply_theme()

    # ── Referencia ─────────────────────────────────────────────────────────────

    def _get_ref(self):
        return self.ref_tab.build_lookup()

    def _on_ref_changed(self):
        records, id_col, disp_col = self.ref_tab.build_lookup()
        n = len(records)
        if n:
            self._ref_status.setText(f"Referencia: {n} registros · ID={id_col} · Texto={disp_col}")
        else:
            self._ref_status.setText("Referencia: sin datos")

    # ── Sesión ─────────────────────────────────────────────────────────────────

    def _save_session(self):
        self.cfg.save_session(
            self.work_tab.get_open_paths(),
            self.ref_tab.get_open_paths()
        )
        self.cfg.save_geometry(self.saveGeometry())

    def _restore_session(self):
        geom = self.cfg.load_geometry()
        if geom:
            self.restoreGeometry(geom)
        work_files, ref_files = self.cfg.load_session()
        self.ref_tab.restore_files(ref_files)
        self.work_tab.restore_files(work_files)

    def closeEvent(self, event):
        self._save_session()
        super().closeEvent(event)
