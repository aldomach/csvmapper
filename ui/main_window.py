"""ui/main_window.py — Ventana principal."""
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QLabel,
    QPushButton, QHBoxLayout, QWidget, QVBoxLayout,
)
from PySide6.QtCore import QTimer

from core.config_manager import ConfigManager
from core.theme import THEMES
from ui.work_tab import WorkTab
from ui.ref_tab import RefTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CSVMapper")
        self.resize(1280, 780)
        self.setMinimumSize(900, 550)

        self.cfg    = ConfigManager()
        self._theme = self.cfg.load_theme()
        self._build_ui()
        self._apply_theme()
        self._restore_session()

        self._save_timer = QTimer(self)
        self._save_timer.timeout.connect(self._save_session)
        self._save_timer.start(30_000)

    def _build_ui(self):
        self.ref_tab  = RefTab(self.cfg, self._get_theme)
        self.ref_tab.ref_changed.connect(self._on_ref_changed)

        self.work_tab = WorkTab(self.cfg, self._get_ref, self._get_theme)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.work_tab, "📋  Trabajo")
        self.tabs.addTab(self.ref_tab,  "📚  Referencia")

        # Barra superior con toggle de tema
        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("btn_theme")
        self.btn_theme.setFixedSize(130, 30)
        self.btn_theme.clicked.connect(self._toggle_theme)

        top_bar = QWidget()
        tbl = QHBoxLayout(top_bar)
        tbl.setContentsMargins(6, 4, 6, 0)
        tbl.addStretch()
        tbl.addWidget(self.btn_theme)

        central = QWidget()
        vl = QVBoxLayout(central)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)
        vl.addWidget(top_bar)
        vl.addWidget(self.tabs)
        self.setCentralWidget(central)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self._ref_status = QLabel("Referencia: sin datos")
        self.status.addPermanentWidget(self._ref_status)
        self.status.showMessage("Listo  ·  Ordenar: clic en encabezado  ·  Buscar: doble clic en columna Coincidencia")

    def _get_theme(self) -> str:
        return self._theme

    def _get_ref(self):
        return self.ref_tab.build_lookup()

    def _apply_theme(self):
        self.setStyleSheet(THEMES[self._theme])
        self.btn_theme.setText(
            "🌙  Modo oscuro" if self._theme == "light" else "☀️  Modo claro"
        )
        if hasattr(self, "work_tab"):
            self.work_tab.refresh_theme()
        if hasattr(self, "ref_tab"):
            self.ref_tab.refresh_theme()

    def _toggle_theme(self):
        self._theme = "dark" if self._theme == "light" else "light"
        self.cfg.save_theme(self._theme)
        self._apply_theme()

    def _on_ref_changed(self):
        result = self.ref_tab.build_lookup()
        records, id_col = result[0], result[1]
        search_cols = result[2] if len(result) > 2 else []
        n = len(records)
        search_info = f" · Buscar en: {', '.join(search_cols)}" if search_cols else ""
        self._ref_status.setText(
            f"Referencia: {n} registros · ID={id_col}{search_info}"
            if n else "Referencia: sin datos"
        )

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
