"""
autocomplete_delegate.py
Delegate con popup de autocompletado que NO usa Qt.Popup (evita robar foco).
Busqueda multi-termino: "anca aña" matchea registros que contengan TODAS las palabras.
"""
from PySide6.QtWidgets import (
    QStyledItemDelegate, QLineEdit, QListWidget, QListWidgetItem,
    QFrame, QVBoxLayout
)
from PySide6.QtCore import Qt, QPoint, QTimer, QEvent
from PySide6.QtGui import QKeyEvent, QColor


class AutocompletePopup(QFrame):
    """
    Popup sin Qt.Popup flag para evitar que cierre el editor al recibir foco.
    Se posiciona manualmente como hijo de la ventana principal.
    """
    def __init__(self, window):
        # Hijo directo de la ventana → no roba foco del editor
        super().__init__(window, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(1, 1, 1, 1)
        lay.setSpacing(0)
        self.list = QListWidget()
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setMouseTracking(True)
        lay.addWidget(self.list)
        self.setFixedHeight(240)
        self.setMinimumWidth(380)

    def show_below(self, editor: QLineEdit):
        gp = editor.mapToGlobal(QPoint(0, editor.height() + 2))
        # Convertir a coordenadas del parent (la ventana)
        lp = self.parent().mapFromGlobal(gp)
        self.move(lp)
        w = max(380, editor.width())
        self.setFixedWidth(w)
        self.raise_()
        self.show()


class AutocompleteDelegate(QStyledItemDelegate):
    def __init__(self, ref_tab_getter, theme_getter=None, parent=None):
        super().__init__(parent)
        self._get_ref = ref_tab_getter
        self._get_theme = theme_getter  # callable → "light"|"dark"
        self._popup: AutocompletePopup | None = None
        self._editor: QLineEdit | None = None
        self._current_index = None
        self._model = None
        self._selected_display = None
        self._selected_id = None
        self._ignore_text_change = False

    # ── Editor lifecycle ───────────────────────────────────────────────────────

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setPlaceholderText("Escribí para buscar…")
        self._editor = editor
        self._current_index = index
        self._model = index.model()
        self._selected_display = None
        self._selected_id = None

        # Crear popup como hijo de la ventana principal
        window = parent.window()
        popup = AutocompletePopup(window)
        self._popup = popup
        self._apply_popup_theme()

        popup.list.itemClicked.connect(self._on_item_selected)
        popup.list.itemActivated.connect(self._on_item_selected)

        editor.textChanged.connect(self._on_text_changed)
        editor.installEventFilter(self)
        popup.list.installEventFilter(self)
        return editor

    def setEditorData(self, editor, index):
        val = index.data(Qt.EditRole) or ""
        self._ignore_text_change = True
        editor.setText(val)
        self._ignore_text_change = False

    def setModelData(self, editor, model, index):
        # Si el usuario seleccionó un item, usar ese valor
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
                QListWidget { background:#2d2d2d; color:#e8e8e8; border:none; font-size:13px; }
                QListWidget::item { padding:6px 10px; color:#e8e8e8; }
                QListWidget::item:hover { background:#3a5278; color:#ffffff; }
                QListWidget::item:selected { background:#1565c0; color:#ffffff; }
            """)
        else:
            self._popup.setStyleSheet("""
                QFrame { background:#ffffff; border:1px solid #90caf9; border-radius:4px; }
                QListWidget { background:#ffffff; color:#1a1a2e; border:none; font-size:13px; }
                QListWidget::item { padding:6px 10px; color:#1a1a2e; }
                QListWidget::item:hover { background:#e3f2fd; color:#0d47a1; }
                QListWidget::item:selected { background:#1565c0; color:#ffffff; }
            """)

    # ── Búsqueda multi-término ────────────────────────────────────────────────

    def _multi_match(self, query: str, record: dict) -> bool:
        """
        Splitea el query en palabras y verifica que CADA palabra
        aparezca en algún campo del registro (búsqueda AND multi-término).
        "anca aña" → busca "anca" Y "aña" en cualquier campo del registro.
        """
        terms = [t.lower() for t in query.split() if t]
        if not terms:
            return False
        haystack = " ".join(str(v) for v in record.values()).lower()
        return all(term in haystack for term in terms)

    def _on_text_changed(self, text: str):
        if self._ignore_text_change:
            return
        # Si el usuario modifica el texto después de seleccionar, resetear selección
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
                # Construir label con todos los campos visibles
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

    def _on_item_selected(self, item: QListWidgetItem):
        display, id_val = item.data(Qt.UserRole)
        self._selected_display = display
        self._selected_id = id_val

        # Escribir en el editor sin re-disparar búsqueda
        if self._editor:
            self._ignore_text_change = True
            self._editor.setText(display)
            self._ignore_text_change = False

        # Escribir ID en la última columna inmediatamente
        self._write_id(id_val)

        if self._popup:
            self._popup.hide()

        # Devolver foco al editor y confirmar
        if self._editor:
            self._editor.setFocus()
            QTimer.singleShot(50, self._commit_and_close)

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
        if event.type() == QEvent.KeyPress:
            key = event.key()

            # Navegación desde el editor hacia el popup
            if obj is self._editor:
                if key == Qt.Key_Down and self._popup and self._popup.isVisible():
                    self._popup.list.setFocus()
                    if self._popup.list.currentRow() < 0:
                        self._popup.list.setCurrentRow(0)
                    return True
                if key == Qt.Key_Escape and self._popup:
                    self._popup.hide()
                    return True
                if key in (Qt.Key_Return, Qt.Key_Enter):
                    if self._popup and self._popup.isVisible():
                        cur = self._popup.list.currentItem()
                        if cur is None and self._popup.list.count() > 0:
                            self._popup.list.setCurrentRow(0)
                            cur = self._popup.list.currentItem()
                        if cur:
                            self._on_item_selected(cur)
                            return True

            # Navegación dentro del popup con teclado
            if obj is self._popup.list if self._popup else False:
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
                # Letras → redirigir al editor
                if key not in (Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown):
                    if self._editor:
                        self._editor.setFocus()
                        self._editor.event(event)
                    return True

        return super().eventFilter(obj, event)
