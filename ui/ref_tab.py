"""
ui/ref_tab.py — Pestaña de referencia.

Nuevas features:
  - Checkboxes para seleccionar en qué campos se busca (multi-campo).
  - Checkboxes para qué columnas se copian al archivo de trabajo al seleccionar.
  - Opción "Solo ID" para copiar únicamente el ID.

build_lookup() devuelve:
  (records, id_col, search_cols, copy_cols)
  - search_cols: lista de columnas donde se busca
  - copy_cols:   lista de (col_ref, col_trabajo) a copiar además del ID
"""
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableView, QComboBox, QFileDialog, QMessageBox, QSizePolicy,
    QFrame, QHeaderView, QAbstractItemView, QCheckBox, QScrollArea,
    QGroupBox, QGridLayout,
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
        self._files: dict = {}          # path → (headers, rows)
        self._current_path = None
        # checkboxes dinámicos
        self._search_checks: list[QCheckBox] = []   # campos de búsqueda
        self._copy_checks:   list[QCheckBox] = []   # columnas a copiar
        self._build_ui()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        # Barra de archivo
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

        # Columna ID
        id_row = QHBoxLayout()
        self.id_combo = QComboBox()
        self.id_combo.setMinimumWidth(160)
        self.id_combo.currentIndexChanged.connect(lambda _: self.ref_changed.emit())
        id_row.addWidget(QLabel("Columna ID:"))
        id_row.addWidget(self.id_combo)
        id_row.addStretch()
        root.addLayout(id_row)

        # Panel de checkboxes en dos grupos lado a lado
        panels = QHBoxLayout()
        panels.setSpacing(12)

        # Grupo: campos de búsqueda
        self._search_group = QGroupBox("Campos para buscar (la búsqueda se hace en estos campos)")
        search_inner = QVBoxLayout(self._search_group)
        self._search_scroll = QScrollArea()
        self._search_scroll.setWidgetResizable(True)
        self._search_scroll.setMaximumHeight(110)
        self._search_container = QWidget()
        self._search_layout = QGridLayout(self._search_container)
        self._search_layout.setSpacing(2)
        self._search_scroll.setWidget(self._search_container)
        search_inner.addWidget(self._search_scroll)

        btn_row_s = QHBoxLayout()
        btn_all_s = QPushButton("Todos")
        btn_all_s.setObjectName("btn_small")
        btn_all_s.setFixedHeight(24)
        btn_none_s = QPushButton("Ninguno")
        btn_none_s.setObjectName("btn_small")
        btn_none_s.setFixedHeight(24)
        btn_all_s.clicked.connect(lambda: self._toggle_all(self._search_checks, True))
        btn_none_s.clicked.connect(lambda: self._toggle_all(self._search_checks, False))
        btn_row_s.addWidget(btn_all_s)
        btn_row_s.addWidget(btn_none_s)
        btn_row_s.addStretch()
        search_inner.addLayout(btn_row_s)
        panels.addWidget(self._search_group)

        # Grupo: columnas a copiar a trabajo
        self._copy_group = QGroupBox("Columnas a copiar al archivo de trabajo al seleccionar")
        copy_inner = QVBoxLayout(self._copy_group)

        # Checkbox "solo ID"
        self._only_id_chk = QCheckBox("Solo copiar el ID (no agregar columnas extra)")
        self._only_id_chk.setChecked(False)
        self._only_id_chk.stateChanged.connect(self._on_only_id_changed)
        copy_inner.addWidget(self._only_id_chk)

        self._copy_scroll = QScrollArea()
        self._copy_scroll.setWidgetResizable(True)
        self._copy_scroll.setMaximumHeight(80)
        self._copy_container = QWidget()
        self._copy_layout = QGridLayout(self._copy_container)
        self._copy_layout.setSpacing(2)
        self._copy_scroll.setWidget(self._copy_container)
        copy_inner.addWidget(self._copy_scroll)

        btn_row_c = QHBoxLayout()
        btn_all_c = QPushButton("Todos")
        btn_all_c.setObjectName("btn_small")
        btn_all_c.setFixedHeight(24)
        btn_none_c = QPushButton("Ninguno")
        btn_none_c.setObjectName("btn_small")
        btn_none_c.setFixedHeight(24)
        btn_all_c.clicked.connect(lambda: self._toggle_all(self._copy_checks, True))
        btn_none_c.clicked.connect(lambda: self._toggle_all(self._copy_checks, False))
        btn_row_c.addWidget(btn_all_c)
        btn_row_c.addWidget(btn_none_c)
        btn_row_c.addStretch()
        copy_inner.addLayout(btn_row_c)
        panels.addWidget(self._copy_group)

        root.addLayout(panels)

        # Separador
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        # Tabla
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

    # ── Checkboxes ─────────────────────────────────────────────────────────────

    def _rebuild_checkboxes(self, headers: list[str]):
        """Recrea los checkboxes de búsqueda y copia según los encabezados."""
        id_col = self.id_combo.currentText()

        # Limpiar
        for chk in self._search_checks + self._copy_checks:
            chk.deleteLater()
        self._search_checks.clear()
        self._copy_checks.clear()

        cols_per_row = 3

        for i, h in enumerate(headers):
            # Búsqueda: todos tildados por defecto excepto el ID
            chk_s = QCheckBox(h)
            chk_s.setChecked(h != id_col)
            chk_s.stateChanged.connect(lambda _: self.ref_changed.emit())
            self._search_layout.addWidget(chk_s, i // cols_per_row, i % cols_per_row)
            self._search_checks.append(chk_s)

            # Copia: excluir el ID (ya se copia siempre)
            if h != id_col:
                chk_c = QCheckBox(h)
                chk_c.setChecked(False)
                j = len(self._copy_checks)
                self._copy_layout.addWidget(chk_c, j // cols_per_row, j % cols_per_row)
                self._copy_checks.append(chk_c)

        self._update_copy_enabled()

    def _toggle_all(self, checks: list[QCheckBox], state: bool):
        for chk in checks:
            chk.setChecked(state)
        self.ref_changed.emit()

    def _on_only_id_changed(self, _):
        self._update_copy_enabled()
        self.ref_changed.emit()

    def _update_copy_enabled(self):
        only_id = self._only_id_chk.isChecked()
        for chk in self._copy_checks:
            chk.setEnabled(not only_id)
        self._copy_scroll.setEnabled(not only_id)

    # ── Archivo ────────────────────────────────────────────────────────────────

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
                self._load_path(p, delimiter=dlg.delimiter,
                                has_header=dlg.has_header, quotechar=dlg.quotechar)
            else:
                self._load_path(p)

    def _load_path(self, path: str, delimiter=None, has_header=True, quotechar='"'):
        try:
            headers, rows, truncated = csv_loader.load_file(
                path, delimiter=delimiter, has_header=has_header
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar:\n{e}")
            return
        if truncated:
            QMessageBox.warning(self, "Archivo grande",
                f"Se cargaron solo las primeras {csv_loader.MAX_ROWS:,} filas.")
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
            for chk in self._search_checks + self._copy_checks:
                chk.deleteLater()
            self._search_checks.clear()
            self._copy_checks.clear()
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

        # Reconstruir ID combo
        self.id_combo.blockSignals(True)
        self.id_combo.clear()
        self.id_combo.addItems(headers)
        self.id_combo.blockSignals(False)

        self._rebuild_checkboxes(headers)
        self.ref_changed.emit()

    # ── API pública ────────────────────────────────────────────────────────────

    def refresh_theme(self):
        if self.table.model():
            self.table.viewport().update()

    def get_open_paths(self) -> list:
        return list(self._files.keys())

    def restore_files(self, paths: list):
        for p in paths:
            self._load_path(p)

    def build_lookup(self) -> tuple:
        """
        Devuelve (records, id_col, search_cols, copy_cols).
        - search_cols: columnas tildadas en "Campos para buscar"
        - copy_cols:   columnas tildadas en "Columnas a copiar" (vacío si solo ID)
        """
        if not self._current_path or self._current_path not in self._files:
            return [], "", [], []
        headers, rows = self._files[self._current_path]
        id_col = self.id_combo.currentText()
        records = [dict(zip(headers, row)) for row in rows]

        search_cols = [
            chk.text() for chk in self._search_checks if chk.isChecked()
        ] or headers  # fallback: todos

        if self._only_id_chk.isChecked():
            copy_cols = []
        else:
            copy_cols = [chk.text() for chk in self._copy_checks if chk.isChecked()]

        return records, id_col, search_cols, copy_cols
