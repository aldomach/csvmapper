"""
autocomplete_delegate.py
Fixes aplicados:
  1. Enter avanza a la fila siguiente, misma columna, abre editor.
  2. Popup redimensionable (QSizeGrip) y posicionado bajo la celda editada.
  3. Flechas ↑↓ navegan toda la lista sin trabarse.
  4. Clic carga el valor correctamente.
"""
from PySide6.QtWidgets import (
    QStyledItemDelegate, QLineEdit, QListWidget, QListWidgetItem,
    QFrame, QVBoxLayout, QSizeGrip, QHBoxLayout, QAbstractItemView
)
from PySide6.QtCore import Qt, QPoint, QTimer, QEvent, QSize
from PySide6.QtGui import QKeyEvent


# ── Popup redimensionable ──────────────────────────────────────────────────────

class AutocompletePopup(QFrame):
    def __init__(self, window):
        super().__init__(window, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)

        root = QVBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 4)
        root.setSpacing(0)

        self.list = QListWidget()
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list.setMouseTracking(True)
        # Flechas navegan la lista normalmente (no interceptadas aquí)
        self.list.setFocusPolicy(Qt.StrongFocus)
        root.addWidget(self.list)

        # Grip en esquina inferior derecha para redimensionar
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 2, 0)
        grip_row.addStretch()
        grip = QSizeGrip(self)
        grip_row.addWidget(grip)
        root.addLayout(grip_row)

        self.resize(420, 260)
        self.setMinimumSize(250, 120)

    def show_below(self, editor: QLineEdit):
        """Posiciona el popup justo debajo de la celda editada."""
        gp = editor.mapToGlobal(QPoint(0, editor.height() + 2))
        lp = self.parent().mapFromGlobal(gp)

        # Ajustar ancho mínimo al ancho del editor
        w = max(self.width(), editor.width())
        self.resize(w, self.height())
        self.move(lp)
        self.raise_()
        self.show()


# ── Delegate ───────────────────────────────────────────────────────────────────

class AutocompleteDelegate(QStyledItemDelegate):
    def __init__(self, ref_tab_getter, theme_getter=None, parent=None):
        super().__init__(parent)
        self._get_ref = ref_tab_getter
        self._get_theme = theme_getter
        self._popup: AutocompletePopup | None = None
        self._editor: QLineEdit | None = None
        self._table = parent          # QTableView
        self._current_index = None
        self._model = None
        self._selected_display = None
        self._selected_id = None
        self._ignore_text_change = False

    # ── Ciclo de vida del editor ───────────────────────────────────────────────

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setPlaceholderText("Escribí para buscar…")
        self._editor = editor
        self._current_index = index
        self._model = index.model()
        self._selected_display = None
        self._selected_id = None

        window = parent.window()
        popup = AutocompletePopup(window)
        self._popup = popup
        self._apply_popup_theme()

        # CLIC: usar pressed en lugar de clicked para capturar antes del foco
        popup.list.itemPressed.connect(self._on_item_selected)

        editor.textChanged.connect(self._on_text_changed)
        editor.installEventFilter(self)
        popup.list.installEventFilter(self)
        return editor

    def setEditorData(self, editor, index):
        val = index.data(Qt.EditRole) or ""
        self._ignore_text_change = True
        editor.setText(val)
        editor.selectAll()
        self._ignore_text_change = False

    def setModelData(self, editor, model, index):
        if self._selected_display is not None:
            model.setData(index, self._selected_display, Qt.EditRole)
        else:
            model.setData(index, editor.text(), Qt.EditRole)

    def destroyEditor(self, editor, index):
        if self._popup:
            self._popup.hide()
            self._popup.deleteLater()
            self._popup = None
        self._editor = None
        super().destroyEditor(editor, index)

    # ── Tema ──────────────────────────────────────────────────────────────────

    def _apply_popup_theme(self):
        if not self._popup:
            return
        dark = self._get_theme and self._get_theme() == "dark"
        if dark:
            self._popup.setStyleSheet("""
                QFrame { background:#2d2d2d; border:1px solid #555; border-radius:4px; }
                QListWidget { background:#2d2d2d; color:#e8e8e8; border:none; font-size:13px; outline:0; }
                QListWidget::item { padding:6px 10px; color:#e8e8e8; }
                QListWidget::item:hover { background:#3a5278; color:#ffffff; }
                QListWidget::item:selected { background:#1565c0; color:#ffffff; }
                QSizeGrip { background: transparent; }
            """)
        else:
            self._popup.setStyleSheet("""
                QFrame { background:#ffffff; border:1px solid #90caf9; border-radius:4px; }
                QListWidget { background:#ffffff; color:#1a1a2e; border:none; font-size:13px; outline:0; }
                QListWidget::item { padding:6px 10px; color:#1a1a2e; }
                QListWidget::item:hover { background:#e3f2fd; color:#0d47a1; }
                QListWidget::item:selected { background:#1565c0; color:#ffffff; }
                QSizeGrip { background: transparent; }
            """)

    # ── Búsqueda multi-término ────────────────────────────────────────────────

    def _multi_match(self, query: str, record: dict) -> bool:
        terms = [t.lower() for t in query.split() if t]
        if not terms:
            return False
        haystack = " ".join(str(v) for v in record.values()).lower()
        return all(term in haystack for term in terms)

    def _on_text_changed(self, text: str):
        if self._ignore_text_change:
            return
        self._selected_display = None
        self._selected_id = None

        query = text.strip()
        if not query or not self._popup:
            if self._popup:
                self._popup.hide()
            return

        records, id_col, disp_col = self._get_ref()
        if not records:
            return

        matches = []
        for rec in records:
            if self._multi_match(query, rec):
                display = rec.get(disp_col, "")
                id_val  = rec.get(id_col, "")
                all_vals = " | ".join(str(v) for v in rec.values())
                matches.append((display, id_val, all_vals))

        self._popup.list.clear()
        for display, id_val, all_vals in matches[:80]:
            item = QListWidgetItem(all_vals)
            item.setData(Qt.UserRole, (display, id_val))
            self._popup.list.addItem(item)

        if matches and self._editor:
            self._apply_popup_theme()
            self._popup.show_below(self._editor)
        else:
            self._popup.hide()

    # ── Selección de item ─────────────────────────────────────────────────────

    def _on_item_selected(self, item: QListWidgetItem):
        if item is None:
            return
        data = item.data(Qt.UserRole)
        if data is None:
            return
        display, id_val = data
        self._selected_display = display
        self._selected_id = id_val

        if self._editor:
            self._ignore_text_change = True
            self._editor.setText(display)
            self._ignore_text_change = False

        self._write_id(id_val)

        if self._popup:
            self._popup.hide()

        if self._editor:
            self._editor.setFocus()

        # Guardar índice actual antes de que se destruya el editor
        current_index = self._current_index
        QTimer.singleShot(30, lambda: self._commit_and_advance(current_index))

    def _commit_and_advance(self, index):
        """Confirma el editor y salta a la siguiente fila, misma columna."""
        if self._editor:
            self.commitData.emit(self._editor)
            self.closeEditor.emit(self._editor, QStyledItemDelegate.NoHint)

        # Avanzar a la siguiente fila
        if index is not None and self._table is not None:
            next_row = index.row() + 1
            col = index.column()
            model = self._table.model()
            if model and next_row < model.rowCount():
                next_index = model.index(next_row, col)
                self._table.setCurrentIndex(next_index)
                self._table.scrollTo(next_index)
                # Abrir editor en la nueva celda
                QTimer.singleShot(30, lambda: self._table.edit(next_index))

    def _commit_and_close(self):
        if self._editor:
            self.commitData.emit(self._editor)
            self.closeEditor.emit(self._editor, QStyledItemDelegate.NoHint)

    def _write_id(self, id_val: str):
        if self._current_index is None or self._model is None:
            return
        row = self._current_index.row()
        last_col = self._model.columnCount() - 1
        self._model.setData(self._model.index(row, last_col), id_val, Qt.EditRole)

    # ── Event filter ──────────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if event.type() != QEvent.KeyPress:
            return super().eventFilter(obj, event)

        key = event.key()

        # ── Teclas en el editor ───────────────────────────────────────────────
        if obj is self._editor:
            popup_visible = self._popup and self._popup.isVisible()

            if key == Qt.Key_Down and popup_visible:
                # Pasar foco al popup, seleccionar primer item
                lst = self._popup.list
                lst.setFocus()
                if lst.currentRow() < 0 and lst.count() > 0:
                    lst.setCurrentRow(0)
                return True

            if key == Qt.Key_Escape:
                if popup_visible:
                    self._popup.hide()
                    return True

            if key in (Qt.Key_Return, Qt.Key_Enter):
                if popup_visible:
                    lst = self._popup.list
                    cur = lst.currentItem()
                    if cur is None and lst.count() > 0:
                        lst.setCurrentRow(0)
                        cur = lst.currentItem()
                    if cur:
                        self._on_item_selected(cur)
                        return True
                # Sin popup: Enter avanza igual
                current_index = self._current_index
                QTimer.singleShot(30, lambda: self._commit_and_advance(current_index))
                return True

        # ── Teclas en la lista del popup ──────────────────────────────────────
        if self._popup and obj is self._popup.list:
            if key in (Qt.Key_Return, Qt.Key_Enter):
                cur = self._popup.list.currentItem()
                if cur:
                    self._on_item_selected(cur)
                return True

            if key == Qt.Key_Escape:
                self._popup.hide()
                if self._editor:
                    self._editor.setFocus()
                return True

            # ↑ y ↓ los deja pasar para que QListWidget los maneje normalmente
            if key in (Qt.Key_Up, Qt.Key_Down,
                       Qt.Key_PageUp, Qt.Key_PageDown,
                       Qt.Key_Home, Qt.Key_End):
                return False   # NO interceptar → navegación nativa de la lista

            # Cualquier letra → redirigir al editor para seguir escribiendo
            if self._editor and event.text():
                self._editor.setFocus()
                self._editor.event(event)
                return True

        return super().eventFilter(obj, event)
