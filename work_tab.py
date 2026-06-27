"""
work_tab.py - Work tab: open CSVs, display as editable tables,
with autocomplete column and auto-filled ID column.
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableView, QComboBox, QFileDialog, QMessageBox, QSizePolicy,
    QFrame, QHeaderView, QAbstractItemView, QInputDialog, QLineEdit
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor, QFont

import csv_loader
from autocomplete_delegate import AutocompleteDelegate

# Column name constants
COL_MATCH = "Coincidencia"
COL_ID    = "ID Referencia"


# ── Editable table model ───────────────────────────────────────────────────────

class EditableCsvModel(QAbstractTableModel):
    def __init__(self, headers: list[str], rows: list[list[str]], parent=None):
        super().__init__(parent)
        self._headers = list(headers) + [COL_MATCH, COL_ID]
        self._rows = [list(r) + ["", ""] for r in rows]

    # Required overrides
    def rowCount(self, _=QModelIndex()): return len(self._rows)
    def columnCount(self, _=QModelIndex()): return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        col = index.column()
        if role in (Qt.DisplayRole, Qt.EditRole):
            return self._rows[index.row()][col]
        if role == Qt.BackgroundRole:
            if col == len(self._headers) - 2:      # COL_MATCH
                return QColor("#fffde7")
            if col == len(self._headers) - 1:      # COL_ID
                return QColor("#e8f5e9")
            if index.row() % 2:
                return QColor("#f5f7fa")
        if role == Qt.FontRole:
            if col >= len(self._headers) - 2:
                f = QFont(); f.setBold(True); return f
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.EditRole and index.isValid():
            self._rows[index.row()][index.column()] = str(value)
            self.dataChanged.emit(index, index)
            return True
        return False

    def flags(self, index):
        base = super().flags(index)
        return base | Qt.ItemIsEditable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    # ── Accessors ──────────────────────────────────────────────────────────────

    def get_headers(self): return list(self._headers)
    def get_rows(self):    return [list(r) for r in self._rows]

    def match_col_index(self): return len(self._headers) - 2
    def id_col_index(self):    return len(self._headers) - 1


# ── Work Tab ───────────────────────────────────────────────────────────────────

class WorkTab(QWidget):
    def __init__(self, config_manager, ref_tab_getter, parent=None):
        super().__init__(parent)
        self.cfg = config_manager
        self._get_ref = ref_tab_getter   # callable → (records, id_col, disp_col)
        self._files: dict[str, EditableCsvModel] = {}
        self._current_path: str | None = None
        self._build_ui()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Toolbar row 1
        bar = QHBoxLayout()
        btn_open   = QPushButton("＋  Abrir CSV")
        btn_open.setFixedHeight(32)
        btn_open.clicked.connect(self._open_file)

        btn_close = QPushButton("✕  Cerrar")
        btn_close.setFixedHeight(32)
        btn_close.clicked.connect(self._close_current)

        btn_export = QPushButton("💾  Exportar CSV")
        btn_export.setFixedHeight(32)
        btn_export.clicked.connect(self._export_current)

        self.file_combo = QComboBox()
        self.file_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.file_combo.currentIndexChanged.connect(self._switch_file)

        bar.addWidget(QLabel("Archivo:"))
        bar.addWidget(self.file_combo)
        bar.addWidget(btn_open)
        bar.addWidget(btn_close)
        bar.addWidget(btn_export)
        root.addLayout(bar)

        # Legend
        legend = QHBoxLayout()
        for color, text in [("#fffde7", f"  {COL_MATCH} (buscar)  "),
                             ("#e8f5e9", f"  {COL_ID} (auto)  ")]:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"background:{color}; border:1px solid #ccc; border-radius:3px; padding:2px 6px;")
            legend.addWidget(lbl)
        legend.addStretch()
        root.addLayout(legend)

        # Separator
        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        # Table
        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked |
            QAbstractItemView.SelectedClicked |
            QAbstractItemView.EditKeyPressed
        )
        root.addWidget(self.table)

        # Status
        self.status_lbl = QLabel("Sin archivos cargados.")
        root.addWidget(self.status_lbl)

    # ── File operations ────────────────────────────────────────────────────────

    def _open_file(self):
        last = self.cfg.load_last_dir()
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Abrir archivo de trabajo", last,
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

        model = EditableCsvModel(headers, rows)
        self._files[path] = model

        name = Path(path).name
        if self.file_combo.findData(path) == -1:
            self.file_combo.addItem(name, userData=path)
        self.file_combo.setCurrentIndex(self.file_combo.findData(path))
        self.cfg.save_last_dir(str(Path(path).parent))

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

    def _export_current(self):
        if not self._current_path:
            QMessageBox.information(self, "Sin datos", "No hay archivo activo para exportar.")
            return
        model = self._files.get(self._current_path)
        if not model:
            return
        default = str(Path(self._current_path).stem) + "_export.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar CSV", default,
            "CSV (*.csv);;Todos (*.*)"
        )
        if not path:
            return
        try:
            csv_loader.save_csv(path, model.get_headers(), model.get_rows())
            QMessageBox.information(self, "Exportado", f"Archivo guardado en:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error al exportar", str(e))

    def _switch_file(self, idx):
        if idx < 0:
            return
        path = self.file_combo.itemData(idx)
        if path not in self._files:
            return
        self._current_path = path
        model = self._files[path]
        self.table.setModel(model)

        # Install autocomplete delegate only on the match column
        delegate = AutocompleteDelegate(self._get_ref, self.table)
        match_col = model.match_col_index()
        self.table.setItemDelegateForColumn(match_col, delegate)

        # ID column: read-only visual indicator (still editable if needed)
        self.table.horizontalHeader().setSectionResizeMode(
            model.id_col_index(), QHeaderView.ResizeToContents
        )
        n_rows = model.rowCount()
        n_cols = model.columnCount()
        self.status_lbl.setText(
            f"{n_rows} filas · {n_cols} columnas  —  {Path(path).name}  "
            f"| Columna '{COL_MATCH}' para buscar, '{COL_ID}' se rellena automático"
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_open_paths(self) -> list[str]:
        return list(self._files.keys())

    def restore_files(self, paths: list[str]):
        for p in paths:
            self._load_path(p)
