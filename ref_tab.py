"""
ref_tab.py - Reference tab: load one or more CSV files, view as tables.
Exposes build_lookup() for the Work tab to use.
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableView, QComboBox, QFileDialog, QMessageBox, QSizePolicy,
    QFrame, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtGui import QFont, QColor
import csv_loader


# ── Thin table model ───────────────────────────────────────────────────────────

class CsvTableModel(QAbstractTableModel):
    def __init__(self, headers, rows, parent=None):
        super().__init__(parent)
        self._headers = headers
        self._rows = rows

    def rowCount(self, _=QModelIndex()):    return len(self._rows)
    def columnCount(self, _=QModelIndex()): return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return self._rows[index.row()][index.column()]
        if role == Qt.BackgroundRole and index.row() % 2:
            return QColor("#f5f7fa")
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None


# ── Reference Tab ──────────────────────────────────────────────────────────────

class RefTab(QWidget):
    """
    Hosts a list of loaded reference files (shown in a QComboBox).
    Exposes build_lookup(id_col, display_col) → dict for the Work tab.
    """
    ref_changed = Signal()   # emitted when reference data is updated

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.cfg = config_manager
        self._files: dict[str, tuple[list, list]] = {}   # path → (headers, rows)
        self._current_path: str | None = None
        self._build_ui()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Toolbar
        bar = QHBoxLayout()
        btn_open = QPushButton("＋  Abrir archivo")
        btn_open.setFixedHeight(32)
        btn_open.clicked.connect(self._open_file)

        btn_close = QPushButton("✕  Cerrar")
        btn_close.setFixedHeight(32)
        btn_close.clicked.connect(self._close_current)

        self.file_combo = QComboBox()
        self.file_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.file_combo.currentIndexChanged.connect(self._switch_file)

        bar.addWidget(QLabel("Archivo:"))
        bar.addWidget(self.file_combo)
        bar.addWidget(btn_open)
        bar.addWidget(btn_close)
        root.addLayout(bar)

        # Column selector row
        col_row = QHBoxLayout()
        self.id_combo  = QComboBox(); self.id_combo.setMinimumWidth(160)
        self.disp_combo = QComboBox(); self.disp_combo.setMinimumWidth(160)
        lbl_info = QLabel("Columna ID:")
        lbl_disp = QLabel("Columna de texto para buscar:")
        col_row.addWidget(lbl_info)
        col_row.addWidget(self.id_combo)
        col_row.addSpacing(20)
        col_row.addWidget(lbl_disp)
        col_row.addWidget(self.disp_combo)
        col_row.addStretch()
        root.addLayout(col_row)

        # Separator
        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        # Table
        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        root.addWidget(self.table)

        # Status
        self.status_lbl = QLabel("Sin archivos cargados.")
        root.addWidget(self.status_lbl)

        self.id_combo.currentIndexChanged.connect(lambda _: self.ref_changed.emit())
        self.disp_combo.currentIndexChanged.connect(lambda _: self.ref_changed.emit())

    # ── File operations ────────────────────────────────────────────────────────

    def _open_file(self):
        last = self.cfg.load_last_dir()
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Abrir archivo de referencia", last,
            "Archivos soportados (*.csv *.tsv *.txt);;Todos (*.*)"
        )
        for p in paths:
            self._load_path(p)

    def _load_path(self, path: str):
        try:
            headers, rows = csv_loader.load_file(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar:\n{e}")
            return
        self._files[path] = (headers, rows)
        name = Path(path).name
        # Avoid duplicates in combo
        if self.file_combo.findData(path) == -1:
            self.file_combo.addItem(name, userData=path)
        self.file_combo.setCurrentIndex(self.file_combo.findData(path))
        self.cfg.save_last_dir(str(Path(path).parent))
        self.ref_changed.emit()

    def _close_current(self):
        idx = self.file_combo.currentIndex()
        if idx < 0:
            return
        path = self.file_combo.currentData()
        self._files.pop(path, None)
        self.file_combo.removeItem(idx)
        if not self._files:
            self.table.setModel(None)
            self.status_lbl.setText("Sin archivos cargados.")
            self.id_combo.clear()
            self.disp_combo.clear()
        self.ref_changed.emit()

    def _switch_file(self, idx):
        if idx < 0:
            return
        path = self.file_combo.itemData(idx)
        if path not in self._files:
            return
        self._current_path = path
        headers, rows = self._files[path]
        model = CsvTableModel(headers, rows)
        self.table.setModel(model)
        self.status_lbl.setText(f"{len(rows)} filas · {len(headers)} columnas  —  {Path(path).name}")
        # Rebuild column combos
        for combo in (self.id_combo, self.disp_combo):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(headers)
            combo.blockSignals(False)
        # Default: first col = ID, second col = display (if available)
        if len(headers) >= 2:
            self.disp_combo.setCurrentIndex(1)
        self.ref_changed.emit()

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_open_paths(self) -> list[str]:
        return list(self._files.keys())

    def restore_files(self, paths: list[str]):
        for p in paths:
            self._load_path(p)

    def build_lookup(self) -> tuple[list[dict], str, str]:
        """
        Returns (records, id_col, display_col).
        records = list of dicts (header → value) for the current reference file.
        """
        if not self._current_path or self._current_path not in self._files:
            return [], "", ""
        headers, rows = self._files[self._current_path]
        id_col   = self.id_combo.currentText()
        disp_col = self.disp_combo.currentText()
        records = [dict(zip(headers, row)) for row in rows]
        return records, id_col, disp_col
