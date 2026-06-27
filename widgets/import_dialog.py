"""
widgets/import_dialog.py — Asistente de importación CSV.
Opciones: separador (incl. comillas+coma y comillas+punto y coma),
si la primera fila es encabezado, preview en tiempo real.
"""
import csv
import io
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QRadioButton, QButtonGroup,
    QLineEdit, QCheckBox, QTableWidget, QTableWidgetItem,
    QGroupBox, QDialogButtonBox, QHeaderView,
)
from PySide6.QtCore import Qt

from core import csv_loader


# Opciones de separador: (etiqueta, delimitador, quotechar)
DELIMITER_OPTIONS = [
    ('Coma  ( , )',                       ',',  '"'),
    ('Punto y coma  ( ; )',               ';',  '"'),
    ('Tab  ( \\t )',                       '\t', '"'),
    ('Pipe  ( | )',                        '|',  '"'),
    ('Entre comillas + coma  "a","b"',    ',',  '"'),   # igual a coma pero lo resalta explícitamente
    ('Entre comillas + punto y coma  "a";"b"', ';', '"'),
    ('Otro…',                              None, '"'),
]


class ImportDialog(QDialog):
    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Asistente de importación")
        self.setMinimumWidth(720)
        self.setMinimumHeight(500)
        self.setModal(True)

        self._filepath = filepath
        self._auto_delim, self._preview_raw = csv_loader.preview_file(filepath, n_rows=8)
        self._sel_delim    = self._auto_delim
        self._sel_quote    = '"'
        self._build_ui()
        self._select_radio(self._auto_delim)
        self._refresh_preview()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # Archivo
        lbl = QLabel(f"<b>Archivo:</b> {self._filepath}")
        lbl.setWordWrap(True)
        root.addWidget(lbl)

        detected = self._delim_label(self._auto_delim)
        root.addWidget(QLabel(f"Separador detectado automáticamente: <b>{detected}</b>"))

        # ── Separador ─────────────────────────────────────────────────────────
        sep_box = QGroupBox("Separador de campos")
        grid = QGridLayout(sep_box)
        grid.setSpacing(4)

        self._btn_group = QButtonGroup(self)
        self._radios: dict = {}   # key → (delim, quote, radio)

        for i, (label, delim, quote) in enumerate(DELIMITER_OPTIONS):
            rb = QRadioButton(label)
            key = (delim, quote)
            self._radios[key] = rb
            self._btn_group.addButton(rb)
            grid.addWidget(rb, i // 2, i % 2)
            rb.toggled.connect(
                lambda checked, d=delim, q=quote: self._on_radio(checked, d, q)
            )

        # Campo personalizado
        custom_row = QHBoxLayout()
        custom_row.addWidget(QLabel("Separador personalizado:"))
        self._custom_edit = QLineEdit()
        self._custom_edit.setPlaceholderText("un carácter")
        self._custom_edit.setMaximumWidth(80)
        self._custom_edit.setEnabled(False)
        self._custom_edit.textChanged.connect(self._on_custom_changed)
        custom_row.addWidget(self._custom_edit)
        custom_row.addStretch()
        grid.addLayout(custom_row, len(DELIMITER_OPTIONS) // 2 + 1, 0, 1, 2)

        root.addWidget(sep_box)

        # ── Encabezado ────────────────────────────────────────────────────────
        self._header_chk = QCheckBox("La primera fila contiene los nombres de columna (encabezado)")
        self._header_chk.setChecked(True)
        self._header_chk.stateChanged.connect(lambda _: self._refresh_preview())
        root.addWidget(self._header_chk)

        # ── Preview ───────────────────────────────────────────────────────────
        root.addWidget(QLabel("<b>Vista previa:</b>"))
        self._preview = QTableWidget()
        self._preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self._preview.setMinimumHeight(200)
        self._preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._preview.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self._preview)

        # ── Botones ───────────────────────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Importar")
        btns.button(QDialogButtonBox.Cancel).setText("Cancelar")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ── Lógica ────────────────────────────────────────────────────────────────

    def _delim_label(self, d: str) -> str:
        return {',': 'coma (,)', ';': 'punto y coma (;)',
                '\t': 'tab', '|': 'pipe (|)'}.get(d, repr(d))

    def _select_radio(self, delim: str):
        key = (delim, '"')
        if key in self._radios:
            self._radios[key].setChecked(True)
        else:
            # Buscar "Otro"
            other_key = (None, '"')
            if other_key in self._radios:
                self._radios[other_key].setChecked(True)
                self._custom_edit.setText(delim)

    def _on_radio(self, checked: bool, delim, quote):
        if not checked:
            return
        is_custom = (delim is None)
        self._custom_edit.setEnabled(is_custom)
        if not is_custom:
            self._sel_delim = delim
            self._sel_quote = quote
            self._refresh_preview()

    def _on_custom_changed(self, text: str):
        if text:
            self._sel_delim = text[0]
            self._sel_quote = '"'
            self._refresh_preview()

    def _refresh_preview(self):
        delim = self._sel_delim or ','
        quote = self._sel_quote or '"'
        has_header = self._header_chk.isChecked()

        # Re-unir las filas raw con el delimitador y re-parsear
        lines = []
        for raw in self._preview_raw:
            if isinstance(raw, list):
                # raw fue parseado antes; re-unir con el delimitador original
                lines.append(delim.join(raw))
            else:
                lines.append(raw)

        parsed = []
        try:
            reader = csv.reader(io.StringIO("\n".join(lines)),
                                delimiter=delim, quotechar=quote)
            for row in reader:
                parsed.append(row)
        except Exception:
            pass

        if not parsed:
            self._preview.clear()
            return

        n_cols = max((len(r) for r in parsed), default=0)
        if has_header:
            headers = parsed[0] + [''] * max(0, n_cols - len(parsed[0]))
            data    = parsed[1:]
        else:
            headers = [f"Col{i+1}" for i in range(n_cols)]
            data    = parsed

        self._preview.setColumnCount(n_cols)
        self._preview.setRowCount(len(data))
        self._preview.setHorizontalHeaderLabels(headers)
        for r, row in enumerate(data):
            for c in range(n_cols):
                val = row[c] if c < len(row) else ""
                self._preview.setItem(r, c, QTableWidgetItem(val))

    # ── Resultado ─────────────────────────────────────────────────────────────

    @property
    def delimiter(self) -> str:
        return self._sel_delim or ','

    @property
    def quotechar(self) -> str:
        return self._sel_quote or '"'

    @property
    def has_header(self) -> bool:
        return self._header_chk.isChecked()
