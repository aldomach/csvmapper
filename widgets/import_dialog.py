"""
widgets/import_dialog.py — Asistente de importación CSV.
Permite elegir separador, si la primera fila es encabezado,
y muestra una preview antes de confirmar.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QRadioButton, QButtonGroup,
    QLineEdit, QCheckBox, QTableWidget, QTableWidgetItem,
    QGroupBox, QDialogButtonBox, QHeaderView
)
from PySide6.QtCore import Qt

from core import csv_loader


DELIMITERS = [
    ("Coma  ( , )",       ","),
    ("Punto y coma  ( ; )", ";"),
    ("Tab  ( \\t )",       "\t"),
    ("Pipe  ( | )",        "|"),
    ("Otro…",             None),
]


class ImportDialog(QDialog):
    """
    Muestra detección automática, permite override manual,
    y presenta preview de las primeras filas.
    """
    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Asistente de importación")
        self.setMinimumWidth(680)
        self.setModal(True)
        self._filepath = filepath
        self._auto_delim, self._preview_raw = csv_loader.preview_file(filepath, n_rows=8)

        self._selected_delim = self._auto_delim
        self._build_ui()
        self._select_radio(self._auto_delim)
        self._refresh_preview()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)

        # Archivo
        file_lbl = QLabel(f"<b>Archivo:</b> {self._filepath}")
        file_lbl.setWordWrap(True)
        root.addWidget(file_lbl)

        auto_lbl = QLabel(
            f"Separador detectado automáticamente: "
            f"<b>{self._delim_label(self._auto_delim)}</b>"
        )
        root.addWidget(auto_lbl)

        # Grupo separador
        sep_group = QGroupBox("Separador de campos")
        sep_layout = QGridLayout(sep_group)
        self._delim_group = QButtonGroup(self)
        self._radios: dict[str | None, QRadioButton] = {}

        for i, (label, delim) in enumerate(DELIMITERS):
            rb = QRadioButton(label)
            self._radios[delim] = rb
            self._delim_group.addButton(rb)
            sep_layout.addWidget(rb, i // 2, i % 2)
            rb.toggled.connect(lambda checked, d=delim: self._on_radio(checked, d))

        # Campo "Otro"
        self._custom_edit = QLineEdit()
        self._custom_edit.setPlaceholderText("Escribí el separador")
        self._custom_edit.setMaximumWidth(120)
        self._custom_edit.setEnabled(False)
        self._custom_edit.textChanged.connect(self._on_custom_changed)
        sep_layout.addWidget(self._custom_edit, len(DELIMITERS) // 2, 1)
        root.addWidget(sep_group)

        # Encabezado
        self._header_check = QCheckBox("La primera fila contiene los nombres de columna (encabezado)")
        self._header_check.setChecked(True)
        self._header_check.stateChanged.connect(lambda _: self._refresh_preview())
        root.addWidget(self._header_check)

        # Preview
        preview_lbl = QLabel("<b>Vista previa:</b>")
        root.addWidget(preview_lbl)
        self._preview_table = QTableWidget()
        self._preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._preview_table.setMinimumHeight(180)
        self._preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        root.addWidget(self._preview_table)

        # Botones
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Importar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ── Lógica ────────────────────────────────────────────────────────────────

    def _delim_label(self, d: str) -> str:
        mapping = {",": "coma (,)", ";": "punto y coma (;)",
                   "\t": "tab", "|": "pipe (|)"}
        return mapping.get(d, repr(d))

    def _select_radio(self, delim: str):
        if delim in self._radios:
            self._radios[delim].setChecked(True)
        else:
            self._radios[None].setChecked(True)
            self._custom_edit.setText(delim)

    def _on_radio(self, checked: bool, delim):
        if not checked:
            return
        is_custom = (delim is None)
        self._custom_edit.setEnabled(is_custom)
        if not is_custom:
            self._selected_delim = delim
            self._refresh_preview()

    def _on_custom_changed(self, text: str):
        if text:
            self._selected_delim = text[0]  # un solo carácter
            self._refresh_preview()

    def _refresh_preview(self):
        import csv as _csv
        delim = self._selected_delim or ","
        has_header = self._header_check.isChecked()

        # Re-parsear el raw preview con el delimitador elegido
        rows = []
        for raw_row in self._preview_raw:
            # raw_row ya es lista; la re-unimos y re-spliteamos
            line = delim.join(raw_row) if isinstance(raw_row, list) else raw_row
            rows.append(line)

        parsed = []
        import io
        text = "\n".join(rows)
        reader = _csv.reader(io.StringIO(text), delimiter=delim)
        for row in reader:
            parsed.append(row)

        if not parsed:
            self._preview_table.clear()
            return

        n_cols = max(len(r) for r in parsed)

        if has_header:
            headers = parsed[0]
            data = parsed[1:]
        else:
            headers = [f"Col{i+1}" for i in range(n_cols)]
            data = parsed

        self._preview_table.setColumnCount(n_cols)
        self._preview_table.setRowCount(len(data))
        self._preview_table.setHorizontalHeaderLabels(headers)

        for r, row in enumerate(data):
            for c, val in enumerate(row):
                self._preview_table.setItem(r, c, QTableWidgetItem(val))

    # ── Resultado ─────────────────────────────────────────────────────────────

    @property
    def delimiter(self) -> str:
        return self._selected_delim or ","

    @property
    def has_header(self) -> bool:
        return self._header_check.isChecked()
