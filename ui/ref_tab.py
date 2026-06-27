"""ui/ref_tab.py — Pestaña de referencia."""
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableView, QComboBox, QFileDialog, QMessageBox, QSizePolicy,
    QFrame, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtGui import QColor

from core import csv_loader
from widgets.import_dialog import ImportDialog


class _ReadOnlyModel(QAbstractTableModel):
    def __init__(self, headers, rows, theme_getter=None, parent=None):
        super().__init__(parent)
        self._h = headers
        self._r = rows
        self._get_theme = theme_getter

    def rowCount(self, _=QModelIndex()):    return len(self._r)
    def columnCount(self, _=QModelIndex()): return len(self._h)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            return self._r[index.row()][index.column()]
        if role == Qt.BackgroundRole and index.row() % 2:
            dark = self._get_theme and self._get_theme() == "dark"
            return QColor("#2a2a42") if dark else QColor("#f5f7fa")
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._h[section]
        return None

    def sort(self, column, order=Qt.AscendingOrder):
        self.layoutAboutToBeChanged.emit()
        self._r.sort(
            key=lambda r: r[column].lower() if column < len(r) else "",
            reverse=(order == Qt.DescendingOrder)
        )
        self.layoutChanged.emit()


class RefTab(QWidget):
    ref_changed = Signal()

    def __init__(self, config_manager, theme_getter=None, parent=None):
        super().__init__(parent)
        self.cfg = config_manager
        self._get_theme = theme_getter
        self._files: dict = {}
        self._current_path = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        bar = QHBoxLayout()
        btn_open = QPushButton("＋  Abrir archivo")
        btn_open.setFixedHeight(32)
        btn_open.clicked.connect(self._open_file)

        btn_close = QPushButton("✕  Cerrar")
        btn_close.setObjectName("btn_close")
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

        col_row = QHBoxLayout()
        self.id_combo   = QComboBox(); self.id_combo.setMinimumWidth(160)
        self.disp_combo = QComboBox(); self.disp_combo.setMinimumWidth(160)
        col_row.addWidget(QLabel("Columna ID:"))
        col_row.addWidget(self.id_combo)
        col_row.addSpacing(16)
        col_row.addWidget(QLabel("Columna de texto para buscar:"))
        col_row.addWidget(self.disp_combo)
        col_row.addStretch()
        root.addLayout(col_row)

        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        root.addWidget(self.table)

        self.status_lbl = QLabel("Sin archivos cargados.")
        root.addWidget(self.status_lbl)

        self.id_combo.currentIndexChanged.connect(lambda _: self.ref_changed.emit())
        self.disp_combo.currentIndexChanged.connect(lambda _: self.ref_changed.emit())

    def _open_file(self):
        last = self.cfg.load_last_dir()
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Abrir archivo de referencia", last,
            "Archivos soportados (*.csv *.tsv *.txt);;Todos (*.*)"
        )
        for p in paths:
            suffix = Path(p).suffix.lower()
            if suffix in (".csv", ".tsv"):
                dlg = ImportDialog(p, parent=self)
                if dlg.exec() != ImportDialog.Accepted:
                    continue
                self._load_path(p, delimiter=dlg.delimiter, has_header=dlg.has_header)
            else:
                self._load_path(p)

    def _load_path(self, path: str, delimiter=None, has_header=True):
        try:
            headers, rows, truncated = csv_loader.load_file(
                path, delimiter=delimiter, has_header=has_header
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar:\n{e}")
            return
        if truncated:
            QMessageBox.warning(
                self, "Archivo grande",
                f"Se cargaron solo las primeras {csv_loader.MAX_ROWS:,} filas."
            )
        self._files[path] = (headers, rows)
        name = Path(path).name
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
        if not path or path not in self._files:
            return
        self._current_path = path
        headers, rows = self._files[path]
        model = _ReadOnlyModel(headers, rows, self._get_theme)
        self.table.setModel(model)
        self.status_lbl.setText(
            f"{len(rows)} filas · {len(headers)} columnas  —  {Path(path).name}"
        )
        for combo in (self.id_combo, self.disp_combo):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(headers)
            combo.blockSignals(False)
        if len(headers) >= 2:
            self.disp_combo.setCurrentIndex(1)
        self.ref_changed.emit()

    def refresh_theme(self):
        if self.table.model():
            self.table.viewport().update()

    def get_open_paths(self) -> list:
        return list(self._files.keys())

    def restore_files(self, paths: list):
        for p in paths:
            self._load_path(p)

    def build_lookup(self) -> tuple:
        if not self._current_path or self._current_path not in self._files:
            return [], "", ""
        headers, rows = self._files[self._current_path]
        id_col   = self.id_combo.currentText()
        disp_col = self.disp_combo.currentText()
        records  = [dict(zip(headers, row)) for row in rows]
        return records, id_col, disp_col
