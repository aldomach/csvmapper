"""
ui/work_tab.py — Pestaña de trabajo.
Features:
  - Asistente de importación (separador + encabezado)
  - Modo solo-mapeo vs edición libre (checkbox)
  - Ordenar por columna (clic en encabezado)
  - Autocompletado con avance automático de fila
"""
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableView, QComboBox, QFileDialog, QMessageBox, QSizePolicy,
    QFrame, QHeaderView, QAbstractItemView, QCheckBox,
)
from PySide6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel,
)
from PySide6.QtGui import QColor, QFont

from core import csv_loader
from widgets.autocomplete_delegate import AutocompleteDelegate
from widgets.import_dialog import ImportDialog

COL_MATCH = "Coincidencia"
COL_ID    = "ID Referencia"


# ── Modelo base editable ───────────────────────────────────────────────────────

class CsvModel(QAbstractTableModel):
    def __init__(self, headers, rows, theme_getter=None, parent=None):
        super().__init__(parent)
        self._headers   = list(headers) + [COL_MATCH, COL_ID]
        self._rows      = [list(r) + ["", ""] for r in rows]
        self._get_theme = theme_getter
        self._match_col = len(self._headers) - 2
        self._id_col    = len(self._headers) - 1
        self._readonly  = True   # modo solo-mapeo por defecto
        self._orig_cols = len(headers)  # columnas originales (no editables en modo readonly)

    # ── Qt API ─────────────────────────────────────────────────────────────────

    def rowCount(self, _=QModelIndex()): return len(self._rows)
    def columnCount(self, _=QModelIndex()): return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        col  = index.column()
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
        base = super().flags(index)
        col  = index.column()
        if self._readonly:
            # Solo las dos columnas nuevas son editables
            if col >= self._match_col:
                return base | Qt.ItemIsEditable
            return base & ~Qt.ItemIsEditable
        return base | Qt.ItemIsEditable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def sort(self, column, order=Qt.AscendingOrder):
        self.layoutAboutToBeChanged.emit()
        reverse = (order == Qt.DescendingOrder)
        self._rows.sort(
            key=lambda r: r[column].lower() if column < len(r) else "",
            reverse=reverse
        )
        self.layoutChanged.emit()

    # ── Modo edición ───────────────────────────────────────────────────────────

    def set_readonly(self, readonly: bool):
        self._readonly = readonly
        self.dataChanged.emit(
            self.index(0, 0),
            self.index(self.rowCount()-1, self.columnCount()-1)
        )

    def add_row(self):
        pos = len(self._rows)
        self.beginInsertRows(QModelIndex(), pos, pos)
        self._rows.append([""] * len(self._headers))
        self.endInsertRows()

    def add_column(self, name: str = "Nueva columna"):
        col = self._match_col  # insertar antes de las columnas de mapeo
        self.beginInsertColumns(QModelIndex(), col, col)
        self._headers.insert(col, name)
        self._match_col += 1
        self._id_col    += 1
        self._orig_cols += 1
        for row in self._rows:
            row.insert(col, "")
        self.endInsertColumns()

    # ── Exportar ───────────────────────────────────────────────────────────────

    def get_headers(self): return list(self._headers)
    def get_rows(self):    return [list(r) for r in self._rows]
    def match_col_index(self): return self._match_col
    def id_col_index(self):    return self._id_col


# ── Work Tab ───────────────────────────────────────────────────────────────────

class WorkTab(QWidget):
    def __init__(self, config_manager, ref_getter, theme_getter=None, parent=None):
        super().__init__(parent)
        self.cfg        = config_manager
        self._get_ref   = ref_getter
        self._get_theme = theme_getter
        self._files     : dict[str, CsvModel] = {}
        self._delegates : dict[str, AutocompleteDelegate] = {}
        self._current_path: str | None = None
        self._build_ui()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        # ── Barra superior ────────────────────────────────────────────────────
        bar = QHBoxLayout()

        self.file_combo = QComboBox()
        self.file_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.file_combo.currentIndexChanged.connect(self._switch_file)

        btn_open = QPushButton("＋  Abrir CSV")
        btn_open.setFixedHeight(32)
        btn_open.clicked.connect(self._open_file)

        btn_close = QPushButton("✕  Cerrar")
        btn_close.setObjectName("btn_close")
        btn_close.setFixedHeight(32)
        btn_close.clicked.connect(self._close_current)

        btn_export = QPushButton("💾  Exportar")
        btn_export.setObjectName("btn_export")
        btn_export.setFixedHeight(32)
        btn_export.clicked.connect(self._export_current)

        bar.addWidget(QLabel("Archivo:"))
        bar.addWidget(self.file_combo)
        bar.addWidget(btn_open)
        bar.addWidget(btn_close)
        bar.addWidget(btn_export)
        root.addLayout(bar)

        # ── Barra de opciones ─────────────────────────────────────────────────
        opts = QHBoxLayout()

        self.chk_readonly = QCheckBox("Solo mapeo (no modificar datos originales)")
        self.chk_readonly.setChecked(True)
        self.chk_readonly.stateChanged.connect(self._on_readonly_changed)
        opts.addWidget(self.chk_readonly)

        opts.addSpacing(20)

        self.btn_add_row = QPushButton("＋ Fila")
        self.btn_add_row.setFixedHeight(26)
        self.btn_add_row.setEnabled(False)
        self.btn_add_row.clicked.connect(self._add_row)

        self.btn_add_col = QPushButton("＋ Columna")
        self.btn_add_col.setFixedHeight(26)
        self.btn_add_col.setEnabled(False)
        self.btn_add_col.clicked.connect(self._add_column)

        opts.addWidget(self.btn_add_row)
        opts.addWidget(self.btn_add_col)
        opts.addStretch()

        # Leyenda
        for color_l, color_d, text in [
            ("#fffde7", "#3d3000", f" 🟡 {COL_MATCH} "),
            ("#e8f5e9", "#003d0f", f" 🟢 {COL_ID} "),
        ]:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"background:{'#3d3000' if False else color_l};"
                "border:1px solid #aaa; border-radius:3px; padding:1px 4px;"
            )
            opts.addWidget(lbl)

        root.addLayout(opts)

        # ── Separador ─────────────────────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        # ── Tabla ─────────────────────────────────────────────────────────────
        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked |
            QAbstractItemView.SelectedClicked |
            QAbstractItemView.EditKeyPressed
        )
        root.addWidget(self.table)

        self.status_lbl = QLabel("Sin archivos cargados.")
        root.addWidget(self.status_lbl)

    # ── Abrir archivo ──────────────────────────────────────────────────────────

    def _open_file(self):
        last = self.cfg.load_last_dir()
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Abrir archivo de trabajo", last,
            "Archivos soportados (*.csv *.tsv *.txt);;Todos (*.*)"
        )
        for p in paths:
            self._open_with_dialog(p)

    def _open_with_dialog(self, path: str):
        suffix = Path(path).suffix.lower()
        if suffix in (".csv", ".tsv"):
            dlg = ImportDialog(path, parent=self)
            if dlg.exec() != ImportDialog.Accepted:
                return
            delimiter  = dlg.delimiter
            has_header = dlg.has_header
        else:
            delimiter  = None
            has_header = True
        self._load_path(path, delimiter=delimiter, has_header=has_header)

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
                self, "Archivo muy grande",
                f"Se cargaron solo las primeras {csv_loader.MAX_ROWS:,} filas."
            )
        model = CsvModel(headers, rows, self._get_theme)
        model.set_readonly(self.chk_readonly.isChecked())
        self._files[path] = model

        name = Path(path).name
        if self.file_combo.findData(path) == -1:
            self.file_combo.addItem(name, userData=path)
        self.file_combo.setCurrentIndex(self.file_combo.findData(path))
        self.cfg.save_last_dir(str(Path(path).parent))

    # ── Cerrar / exportar ──────────────────────────────────────────────────────

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
            QMessageBox.information(self, "Sin datos", "No hay archivo activo.")
            return
        model = self._files.get(self._current_path)
        if not model:
            return
        default = Path(self._current_path).stem + "_export.csv"
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

    # ── Cambiar archivo activo ─────────────────────────────────────────────────

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
        self.status_lbl.setText(
            f"{model.rowCount()} filas · {model.columnCount()} columnas  —  "
            f"{Path(path).name}  |  "
            f"{'Solo mapeo' if self.chk_readonly.isChecked() else 'Edición libre'}  |  "
            f"Doble clic en '{COL_MATCH}' para buscar"
        )

    # ── Modo edición ───────────────────────────────────────────────────────────

    def _on_readonly_changed(self, state):
        readonly = bool(state)
        self.btn_add_row.setEnabled(not readonly)
        self.btn_add_col.setEnabled(not readonly)
        model = self._current_model()
        if model:
            model.set_readonly(readonly)
        self._update_status()

    def _add_row(self):
        model = self._current_model()
        if model:
            model.add_row()
            self._update_status()

    def _add_column(self):
        model = self._current_model()
        if model:
            from PySide6.QtWidgets import QInputDialog
            name, ok = QInputDialog.getText(self, "Nueva columna", "Nombre:")
            if ok and name.strip():
                model.add_column(name.strip())
            self._update_status()

    def _current_model(self) -> CsvModel | None:
        if self._current_path:
            return self._files.get(self._current_path)
        return None

    def _update_status(self):
        model = self._current_model()
        if model and self._current_path:
            self.status_lbl.setText(
                f"{model.rowCount()} filas · {model.columnCount()} columnas  —  "
                f"{Path(self._current_path).name}"
            )

    # ── Tema ───────────────────────────────────────────────────────────────────

    def refresh_theme(self):
        if self.table.model():
            self.table.viewport().update()

    # ── API pública ────────────────────────────────────────────────────────────

    def get_open_paths(self) -> list:
        return list(self._files.keys())

    def restore_files(self, paths: list):
        for p in paths:
            self._load_path(p)
