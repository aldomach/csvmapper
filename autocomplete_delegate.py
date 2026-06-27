"""
autocomplete_delegate.py  —  reescritura completa

Arquitectura:
  - El popup es un QDialog sin bordes, INDEPENDIENTE de la ventana principal.
    Esto resuelve de raíz todos los problemas de foco, scroll y posición.
  - El QDialog tiene WA_ShowWithoutActivating para no robar el foco del editor.
  - Redimensionable con QSizeGrip.
  - Posición calculada en coordenadas globales de pantalla → siempre bajo la celda.
  - Clic usa mousePressEvent en el QListWidget para capturar antes de cualquier
    cambio de foco.
  - Flechas manejadas con eventFilter sobre la lista, devolviendo False para que
    QListWidget las procese nativamente.
  - Enter en editor o en lista confirma y avanza a la siguiente fila.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QStyledItemDelegate, QLineEdit, QListWidget, QListWidgetItem,
    QDialog, QVBoxLayout, QHBoxLayout, QSizeGrip, QAbstractItemView,
    QApplication,
)
from PySide6.QtCore import Qt, QPoint, QRect, QTimer, QEvent, QObject
from PySide6.QtGui  import QKeyEvent


# ─────────────────────────────────────────────────────────────────────────────
#  Popup
# ─────────────────────────────────────────────────────────────────────────────

class _ListView(QListWidget):
    """QListWidget que notifica clics via callback sin cambiar el foco."""
    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        self._on_click = on_click

    def mousePressEvent(self, event):
        # Calcular el item bajo el cursor ANTES de que super() cambie nada
        item = self.itemAt(event.pos())
        if item is not None:
            self._on_click(item)
        else:
            super().mousePressEvent(event)


class AutocompletePopup(QDialog):
    """
    Ventana independiente (QDialog sin bordes) para el autocomplete.
    No roba foco. Redimensionable. Posición global.
    """
    def __init__(self, on_select):
        # Sin parent → ventana independiente del sistema operativo
        super().__init__(None)
        self._on_select = on_select

        # Flags: sin bordes, sin taskbar, siempre encima, no roba foco
        self.setWindowFlags(
            Qt.Tool |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setMinimumSize(300, 120)
        self.resize(500, 280)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 4)
        lay.setSpacing(0)

        self.list = _ListView(self._item_clicked)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setFocusPolicy(Qt.NoFocus)   # ← clave: nunca roba foco
        lay.addWidget(self.list)

        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 2, 0)
        grip_row.addStretch()
        grip_row.addWidget(QSizeGrip(self))
        lay.addLayout(grip_row)

    def _item_clicked(self, item: QListWidgetItem):
        self._on_select(item)

    def position_below(self, editor: QLineEdit):
        """Posiciona el popup justo debajo del editor en coordenadas globales."""
        gp: QPoint = editor.mapToGlobal(QPoint(0, editor.height() + 2))

        # Ajustar ancho al editor si el popup es más angosto
        new_w = max(self.width(), editor.width(), 500)
        self.resize(new_w, self.height())

        # Evitar que se salga de la pantalla por abajo
        screen: QRect = QApplication.primaryScreen().availableGeometry()
        x = max(screen.left(), min(gp.x(), screen.right()  - self.width()))
        y = gp.y()
        if y + self.height() > screen.bottom():
            # Mostrar arriba del editor si no entra abajo
            y = editor.mapToGlobal(QPoint(0, 0)).y() - self.height() - 2
        self.move(x, y)

    def apply_theme(self, dark: bool):
        if dark:
            self.setStyleSheet("""
                QDialog   { background:#2b2b2b; border:1px solid #555; border-radius:4px; }
                QListWidget { background:#2b2b2b; color:#e8e8e8; border:none;
                              font-size:13px; outline:0; }
                QListWidget::item          { padding:5px 10px; color:#e8e8e8; }
                QListWidget::item:hover    { background:#3a5278; color:#fff; }
                QListWidget::item:selected { background:#1565c0; color:#fff; }
                QScrollBar:vertical   { background:#3a3a3a; width:10px; border-radius:5px; }
                QScrollBar::handle:vertical { background:#666; border-radius:5px; }
                QSizeGrip { background:transparent; width:12px; height:12px; }
            """)
        else:
            self.setStyleSheet("""
                QDialog   { background:#fff; border:1px solid #90caf9; border-radius:4px; }
                QListWidget { background:#fff; color:#1a1a2e; border:none;
                              font-size:13px; outline:0; }
                QListWidget::item          { padding:5px 10px; color:#1a1a2e; }
                QListWidget::item:hover    { background:#e3f2fd; color:#0d47a1; }
                QListWidget::item:selected { background:#1565c0; color:#fff; }
                QScrollBar:vertical   { background:#f0f0f0; width:10px; border-radius:5px; }
                QScrollBar::handle:vertical { background:#bbb; border-radius:5px; }
                QSizeGrip { background:transparent; width:12px; height:12px; }
            """)

    def select_next(self):
        n = self.list.count()
        if n == 0:
            return
        row = self.list.currentRow()
        self.list.setCurrentRow(min(row + 1, n - 1))

    def select_prev(self):
        n = self.list.count()
        if n == 0:
            return
        row = self.list.currentRow()
        self.list.setCurrentRow(max(row - 1, 0))

    def current_item(self) -> QListWidgetItem | None:
        return self.list.currentItem()

    def confirm_current(self):
        item = self.current_item()
        if item:
            self._on_select(item)


# ─────────────────────────────────────────────────────────────────────────────
#  Delegate
# ─────────────────────────────────────────────────────────────────────────────

class AutocompleteDelegate(QStyledItemDelegate):
    def __init__(self, ref_tab_getter, theme_getter=None, table=None, parent=None):
        super().__init__(parent)
        self._get_ref     = ref_tab_getter
        self._get_theme   = theme_getter
        self._table       = table          # QTableView — para avanzar filas

        # Estado por sesión de edición
        self._popup        : AutocompletePopup | None = None
        self._editor       : QLineEdit        | None = None
        self._current_index                          = None
        self._model                                  = None
        self._selected_display : str | None          = None
        self._selected_id      : str | None          = None
        self._ignore_text      : bool                = False

    # ── Ciclo de vida ──────────────────────────────────────────────────────────

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setPlaceholderText("Escribí para buscar…")

        self._editor        = editor
        self._current_index = index
        self._model         = index.model()
        self._selected_display = None
        self._selected_id      = None

        # Un solo popup compartido por sesión de edición
        popup = AutocompletePopup(on_select=self._on_item_selected)
        popup.apply_theme(self._get_theme and self._get_theme() == "dark")
        self._popup = popup

        editor.textChanged.connect(self._on_text_changed)
        editor.installEventFilter(self)
        return editor

    def setEditorData(self, editor, index):
        val = index.data(Qt.EditRole) or ""
        self._ignore_text = True
        editor.setText(val)
        editor.selectAll()
        self._ignore_text = False

    def setModelData(self, editor, model, index):
        value = self._selected_display if self._selected_display is not None else editor.text()
        model.setData(index, value, Qt.EditRole)

    def destroyEditor(self, editor, index):
        if self._popup:
            self._popup.hide()
            self._popup.deleteLater()
            self._popup = None
        self._editor = None
        super().destroyEditor(editor, index)

    # ── Búsqueda ──────────────────────────────────────────────────────────────

    @staticmethod
    def _multi_match(query: str, record: dict) -> bool:
        """AND entre términos: todos deben aparecer en algún campo del registro."""
        terms = [t.lower() for t in query.split() if t]
        if not terms:
            return False
        haystack = " ".join(str(v) for v in record.values()).lower()
        return all(t in haystack for t in terms)

    def _on_text_changed(self, text: str):
        if self._ignore_text:
            return
        self._selected_display = None
        self._selected_id      = None

        query = text.strip()
        if not query:
            if self._popup:
                self._popup.hide()
            return

        records, id_col, disp_col = self._get_ref()
        if not records:
            return

        matches = []
        for rec in records:
            if self._multi_match(query, rec):
                display  = str(rec.get(disp_col, ""))
                id_val   = str(rec.get(id_col,   ""))
                label    = "  |  ".join(str(v) for v in rec.values())
                matches.append((display, id_val, label))

        popup = self._popup
        if popup is None:
            return

        popup.list.clear()
        for display, id_val, label in matches[:200]:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, (display, id_val))
            popup.list.addItem(item)

        if not matches:
            popup.hide()
            return

        # Posicionar y mostrar
        if self._editor:
            popup.apply_theme(self._get_theme and self._get_theme() == "dark")
            popup.position_below(self._editor)
            popup.show()
            # Mantener foco en el editor
            self._editor.setFocus()

    # ── Selección ─────────────────────────────────────────────────────────────

    def _on_item_selected(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole)
        if data is None:
            return
        display, id_val = data

        self._selected_display = display
        self._selected_id      = id_val

        # Actualizar editor sin re-disparar búsqueda
        if self._editor:
            self._ignore_text = True
            self._editor.setText(display)
            self._ignore_text = False

        # Escribir ID en última columna inmediatamente
        self._write_id(id_val)

        if self._popup:
            self._popup.hide()

        # Guardar índice antes de que se destruya el editor
        saved_index = self._current_index
        if self._editor:
            self._editor.setFocus()
        QTimer.singleShot(20, lambda: self._commit_and_advance(saved_index))

    def _write_id(self, id_val: str):
        if self._current_index is None or self._model is None:
            return
        last_col = self._model.columnCount() - 1
        idx = self._model.index(self._current_index.row(), last_col)
        self._model.setData(idx, id_val, Qt.EditRole)

    # ── Confirmar y avanzar ────────────────────────────────────────────────────

    def _commit_and_advance(self, index):
        if self._editor:
            self.commitData.emit(self._editor)
            self.closeEditor.emit(self._editor, QStyledItemDelegate.NoHint)

        if index is None or self._table is None:
            return
        model = self._table.model()
        if model is None:
            return
        next_row = index.row() + 1
        col      = index.column()
        if next_row >= model.rowCount():
            return
        next_idx = model.index(next_row, col)
        self._table.setCurrentIndex(next_idx)
        self._table.scrollTo(next_idx)
        QTimer.singleShot(30, lambda: self._table.edit(next_idx))

    # ── Event filter (solo en el editor) ──────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is not self._editor:
            return super().eventFilter(obj, event)
        if event.type() != QEvent.KeyPress:
            return super().eventFilter(obj, event)

        key     = event.key()
        popup   = self._popup
        visible = popup is not None and popup.isVisible()

        # ↓ — seleccionar primer item o mover hacia abajo
        if key == Qt.Key_Down:
            if visible:
                if popup.current_item() is None:
                    popup.list.setCurrentRow(0)
                else:
                    popup.select_next()
            return True

        # ↑ — mover hacia arriba
        if key == Qt.Key_Up:
            if visible:
                popup.select_prev()
            return True

        # Enter / Return — confirmar selección o avanzar fila
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if visible:
                if popup.current_item() is None and popup.list.count() > 0:
                    popup.list.setCurrentRow(0)
                if popup.current_item():
                    popup.confirm_current()
                    return True
            # Sin popup abierto: avanzar igualmente
            saved = self._current_index
            QTimer.singleShot(20, lambda: self._commit_and_advance(saved))
            return True

        # Esc — cerrar popup
        if key == Qt.Key_Escape:
            if visible:
                popup.hide()
                return True

        # Tab — cerrar popup y comportamiento normal
        if key == Qt.Key_Tab:
            if visible:
                popup.hide()

        return super().eventFilter(obj, event)
