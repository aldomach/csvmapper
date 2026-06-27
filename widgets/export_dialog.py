"""
widgets/export_dialog.py — Asistente de exportación.
Permite elegir columnas a exportar y separador de salida.
"""
import csv
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QRadioButton, QButtonGroup,
    QLineEdit, QCheckBox, QGroupBox, QDialogButtonBox,
    QScrollArea, QWidget, QFileDialog,
)
from PySide6.QtCore import Qt

DELIMITER_OPTIONS = [
    ("Coma  ( , )",            ","),
    ("Punto y coma  ( ; )",    ";"),
    ("Tab  ( \\t )",            "\t"),
    ("Pipe  ( | )",             "|"),
    ("Otro…",                   None),
]


class ExportDialog(QDialog):
    def __init__(self, headers: list[str], n_rows: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Asistente de exportación")
        self.setMinimumWidth(600)
        self.setMinimumHeight(480)
        self.setModal(True)

        self._headers    = headers
        self._n_rows     = n_rows
        self._sel_delim  = ","
        self._col_checks : list[QCheckBox] = []
        self._filepath   : str = ""

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        root.addWidget(QLabel(f"<b>{self._n_rows}</b> filas · <b>{len(self._headers)}</b> columnas disponibles"))

        # ── Columnas ──────────────────────────────────────────────────────────
        col_box = QGroupBox("Columnas a exportar")
        col_vlay = QVBoxLayout(col_box)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(180)
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(3)
        cols_per_row = 3

        for i, h in enumerate(self._headers):
            chk = QCheckBox(h)
            chk.setChecked(True)
            grid.addWidget(chk, i // cols_per_row, i % cols_per_row)
            self._col_checks.append(chk)

        scroll.setWidget(container)
        col_vlay.addWidget(scroll)

        # Botones selección rápida
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        for label, fn in [
            ("Todos",    lambda: self._set_all(True)),
            ("Ninguno",  lambda: self._set_all(False)),
            ("Invertir", self._invert),
        ]:
            b = QPushButton(label)
            b.setObjectName("btn_small")
            b.setFixedHeight(24)
            b.clicked.connect(fn)
            btn_row.addWidget(b)
        btn_row.addStretch()
        col_vlay.addLayout(btn_row)
        root.addWidget(col_box)

        # ── Separador de salida ───────────────────────────────────────────────
        sep_box = QGroupBox("Separador de campos en el archivo de salida")
        sep_grid = QGridLayout(sep_box)
        self._delim_group = QButtonGroup(self)
        self._radios: dict = {}

        for i, (label, delim) in enumerate(DELIMITER_OPTIONS):
            rb = QRadioButton(label)
            rb.setChecked(delim == ",")
            self._radios[delim] = rb
            self._delim_group.addButton(rb)
            sep_grid.addWidget(rb, i // 2, i % 2)
            rb.toggled.connect(
                lambda checked, d=delim: self._on_radio(checked, d)
            )

        custom_row = QHBoxLayout()
        custom_row.addWidget(QLabel("Personalizado:"))
        self._custom_edit = QLineEdit()
        self._custom_edit.setPlaceholderText("un carácter")
        self._custom_edit.setMaximumWidth(70)
        self._custom_edit.setEnabled(False)
        self._custom_edit.textChanged.connect(self._on_custom)
        custom_row.addWidget(self._custom_edit)
        custom_row.addStretch()
        sep_grid.addLayout(custom_row, len(DELIMITER_OPTIONS) // 2 + 1, 0, 1, 2)
        root.addWidget(sep_box)

        # ── Botones OK/Cancel ─────────────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Elegir destino y exportar…")
        btns.button(QDialogButtonBox.Cancel).setText("Cancelar")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ── Lógica ────────────────────────────────────────────────────────────────

    def _set_all(self, state: bool):
        for chk in self._col_checks:
            chk.setChecked(state)

    def _invert(self):
        for chk in self._col_checks:
            chk.setChecked(not chk.isChecked())

    def _on_radio(self, checked: bool, delim):
        if not checked:
            return
        is_custom = (delim is None)
        self._custom_edit.setEnabled(is_custom)
        if not is_custom:
            self._sel_delim = delim

    def _on_custom(self, text: str):
        if text:
            self._sel_delim = text[0]

    def _on_accept(self):
        selected = self.selected_columns
        if not selected:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Sin columnas", "Seleccioná al menos una columna.")
            return
        self.accept()

    # ── Resultado ─────────────────────────────────────────────────────────────

    @property
    def selected_columns(self) -> list[str]:
        return [chk.text() for chk in self._col_checks if chk.isChecked()]

    @property
    def delimiter(self) -> str:
        return self._sel_delim or ","
