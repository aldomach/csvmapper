"""
ui_main.py - MainWindow: tab container, session save/restore, theming.
"""
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QStatusBar, QToolBar,
    QApplication, QLabel
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QFont, QAction

from config_manager import ConfigManager
from ref_tab import RefTab
from work_tab import WorkTab


STYLE = """
QMainWindow { background: #f0f2f5; }
QTabWidget::pane { border: 1px solid #d0d3d8; background: #ffffff; border-radius: 4px; }
QTabBar::tab {
    padding: 8px 22px; font-size: 13px; background: #e4e7ec;
    border: 1px solid #c9cdd4; border-bottom: none;
    border-top-left-radius: 4px; border-top-right-radius: 4px;
    color: #555;
}
QTabBar::tab:selected { background: #ffffff; color: #1a1a2e; font-weight: bold; }
QTabBar::tab:hover { background: #f0f2f5; }

QPushButton {
    background: #3f51b5; color: white; border: none;
    border-radius: 4px; padding: 5px 14px; font-size: 12px;
}
QPushButton:hover { background: #5c6bc0; }
QPushButton:pressed { background: #303f9f; }
QPushButton[text="✕  Cerrar"] { background: #e53935; }
QPushButton[text="✕  Cerrar"]:hover { background: #ef5350; }
QPushButton[text="💾  Exportar CSV"] { background: #2e7d32; }
QPushButton[text="💾  Exportar CSV"]:hover { background: #388e3c; }

QTableView {
    gridline-color: #e0e3e8;
    font-size: 12px;
    selection-background-color: #bbdefb;
    selection-color: #000;
}
QTableView QHeaderView::section {
    background: #3f51b5; color: white;
    padding: 5px 8px; border: none;
    font-size: 12px; font-weight: bold;
}
QComboBox {
    border: 1px solid #bbb; border-radius: 3px; padding: 4px 8px; font-size: 12px;
}
QLineEdit {
    border: 1px solid #90caf9; border-radius: 3px; padding: 4px; font-size: 12px;
}
QStatusBar { background: #3f51b5; color: white; font-size: 11px; }
QLabel { font-size: 12px; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CSVMapper")
        self.resize(1200, 750)
        self.setMinimumSize(800, 500)

        self.cfg = ConfigManager()
        self._build_ui()
        self._restore_session()

        # Auto-save every 30 s
        self._save_timer = QTimer(self)
        self._save_timer.timeout.connect(self._save_session)
        self._save_timer.start(30_000)

    # ── Build UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setStyleSheet(STYLE)

        # Reference tab first so Work tab can query it
        self.ref_tab = RefTab(self.cfg)
        self.ref_tab.ref_changed.connect(self._on_ref_changed)

        self.work_tab = WorkTab(self.cfg, self._get_ref)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.work_tab, "📋  Trabajo")
        self.tabs.addTab(self.ref_tab, "📚  Referencia")
        self.setCentralWidget(self.tabs)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self._ref_status = QLabel("Referencia: sin datos")
        self.status.addPermanentWidget(self._ref_status)
        self.status.showMessage("Listo")

    def _get_ref(self):
        return self.ref_tab.build_lookup()

    def _on_ref_changed(self):
        records, id_col, disp_col = self.ref_tab.build_lookup()
        n = len(records)
        if n:
            self._ref_status.setText(f"Referencia: {n} registros · ID={id_col} · Texto={disp_col}")
        else:
            self._ref_status.setText("Referencia: sin datos")

    # ── Session ────────────────────────────────────────────────────────────────

    def _save_session(self):
        self.cfg.save_session(
            self.work_tab.get_open_paths(),
            self.ref_tab.get_open_paths()
        )
        geom = self.saveGeometry()
        self.cfg.save_geometry(geom)

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
