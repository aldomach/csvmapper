"""
work_tab.py - Pestaña de Trabajo con tabla editable y autocompletado.
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableView, QComboBox, QFileDialog, QMessageBox, QSizePolicy,
    QFrame, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor, QFont

import csv_loader
from autocomplete_delegate import AutocompleteDelegate

COL_MATCH = "Coincidencia"
COL_ID    = "ID Referencia"


class EditableCsvModel(QAbstractTableModel):
    def __init__(self, headers, rows, theme_getter=None, parent=None):
        super().__init__(parent)
        self._headers = list(headers) + [COL_MATCH, COL_ID]
        self._rows = [list(r) + ["", ""] for r in rows]
        self._get_theme = theme_getter
        self._match_col = len(self._headers) - 2
        self._id_col    = len(self._headers) - 1

    def rowCount(self, _=QModelIndex()): return len(self._rows)
    def columnCount(self, _=QModelIndex()): return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        col = index.column()
        dark = self._get_theme and self._get_theme() == "dark"

        if role in (Qt.DisplayRole, Qt.EditRole):
            return self._rows[index.row()][col]

        if role == Qt.BackgroundRole:
            if col == self._match_col:
                return QColor("#3d3000") if dark else QColor("#fffde7")
            if col == self._id_col:
                return QColor("#003d0f") if dark else QColor("#e8f5e9")
            if index.row() % 2:
                return QColor("#2a2a42") if dark else QColor("#f5f7fa")

        if role == Qt.ForegroundRole:
            if col == self._match_col:
                return QColor("#ffe082") if dark else QColor("#5d4037")
            if col == self._id_col:
                return QColor("#a5d6a7") if dark else QColor("#1b5e20")

        if role == Qt.FontRole and col >= self._match_col:
            f = QFont(); f.setBold(True); return f

        return None

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.EditRole and index.isValid():
            self._rows[index.row()][index.column()] = str(value)
            self.dataChanged.emit(index, index)
            return True
        return False

    def flags(self, index):
        return super().flags(index) | Qt.ItemIsEditable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def get_headers(self): return list(self._headers)
    def get_rows(self):    return [list(r) for r in self._rows]
    def match_col_index(self): return self._match_col
    def id_col_index(self):    return self._id_col


class WorkTab(QWidget):
    def __init__(self, config_manager, ref_tab_getter, theme_getter=None, parent=None):
        super().__init__(parent)
        self.cfg = config_manager
        self._get_ref = ref_tab_getter
        self._get_theme = theme_getter
        self._files: dict = {}
        self._delegates: dict = {}   # path → delegate (para actualizar tema)
        self._current_path = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        bar = QHBoxLayout()
        btn_open = QPushButton("＋  Abrir CSV")
        btn_open.setFixedHeight(32)
        btn_open.clicked.connect(self._open_file)

        btn_close = QPushButton("✕  Cerrar")
        btn_close.setObjectName("btn_close")
        btn_close.setFixedHeight(32)
        btn_close.clicked.connect(self._close_current)

        btn_export = QPushButton("💾  Exportar CSV")
        btn_export.setObjectName("btn_export")
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

        # Leyenda
        legend = QHBoxLayout()
        self.lbl_match = QLabel(f"  🟡 {COL_MATCH}: escribí para buscar en la referencia  ")
        self.lbl_id    = QLabel(f"  🟢 {COL_ID}: se rellena automático  ")
        for lbl in (self.lbl_match, self.lbl_id):
            lbl.setStyleSheet("border:1px solid #aaa; border-radius:3px; padding:2px 6px;")
            legend.addWidget(lbl)
        legend.addStretch()
        root.addLayout(legend)

        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

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

        self.status_lbl = QLabel("Sin archivos cargados.")
        root.addWidget(self.status_lbl)

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
            headers, rows, truncated = csv_loader.load_file(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar:\n{e}")
            return
        if truncated:
            QMessageBox.warning(
                self, "Archivo muy grande",
                f"El archivo supera {csv_loader.MAX_ROWS:,} filas.\n"
                f"Se cargaron solo las primeras {csv_loader.MAX_ROWS:,} filas."
            )
        model = EditableCsvModel(headers, rows, self._get_theme)
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
        self._delegates.pop(path, None)
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
            self, "Exportar CSV", default, "CSV (*.csv);;Todos (*.*)"
        )
        if not path:
            return
        try:
            csv_loader.save_csv(path, model.get_headers(), model.get_rows())
            QMessageBox.information(self, "Exportado", f"Guardado en:\n{path}")
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

        delegate = AutocompleteDelegate(
            self._get_ref, self._get_theme, table=self.table
        )
        self._delegates[path] = delegate
        self.table.setItemDelegateForColumn(model.match_col_index(), delegate)
        self.table.horizontalHeader().setSectionResizeMode(
            model.id_col_index(), QHeaderView.ResizeToContents
        )
        n = model.rowCount()
        c = model.columnCount()
        self.status_lbl.setText(
            f"{n} filas · {c} columnas  —  {Path(path).name}"
            f"  |  Doble clic en '{COL_MATCH}' para buscar"
        )

    def refresh_theme(self):
        if self.table.model():
            self.table.viewport().update()

    def get_open_paths(self) -> list:
        return list(self._files.keys())

    def restore_files(self, paths: list):
        for p in paths:
            self._load_path(p)
