"""
widgets/autocomplete_delegate.py

Fix definitivo del bug Coincidencia:
  _on_selected escribe DIRECTAMENTE en el modelo (self._model.setData)
  en el momento del clic, SIN esperar a setModelData ni commitData.
  setModelData queda como respaldo para el caso Enter.
  Así el display siempre se guarda independientemente del ciclo del editor.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QStyledItemDelegate, QLineEdit, QListWidget, QListWidgetItem,
    QWidget, QVBoxLayout, QAbstractItemView, QApplication,
)
from PySide6.QtCore import Qt, QPoint, QRect, QTimer, QEvent


# ─────────────────────────────────────────────────────────────────────────────
#  Lista con clic nativo — sin propagar eventos de mouse
# ─────────────────────────────────────────────────────────────────────────────

class _ClickList(QListWidget):
    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        self._on_click = on_click
        self.setFocusPolicy(Qt.NoFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if item is not None:
            self.setCurrentItem(item)
            self._on_click(item)
        event.accept()   # siempre aceptar — nunca propagar al padre

    def mouseReleaseEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        super().wheelEvent(event)
        event.accept()


# ─────────────────────────────────────────────────────────────────────────────
#  Popup — QWidget top-level, sin parent, sin SizeGrip
# ─────────────────────────────────────────────────────────────────────────────

class AutocompletePopup(QWidget):
    def __init__(self, on_select):
        super().__init__(None)
        self._on_select = on_select
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setMinimumSize(500, 160)

        screen_w = QApplication.primaryScreen().availableGeometry().width()
        self.resize(max(700, screen_w // 2), 320)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(1, 1, 1, 1)
        lay.setSpacing(0)
        self.list = _ClickList(self._on_select)
        lay.addWidget(self.list)

    def show_below(self, editor: QLineEdit):
        origin = editor.mapToGlobal(QPoint(0, editor.height() + 3))
        new_w  = max(self.width(), editor.width())
        self.resize(new_w, self.height())
        screen: QRect = QApplication.primaryScreen().availableGeometry()
        x = max(screen.left(), min(origin.x(), screen.right() - self.width()))
        y = origin.y()
        if y + self.height() > screen.bottom():
            y = editor.mapToGlobal(QPoint(0, 0)).y() - self.height() - 3
        y = max(screen.top(), y)
        self.move(x, y)
        self.raise_()
        self.show()

    def select_next(self):
        n = self.list.count()
        if n == 0: return
        self.list.setCurrentRow(min(self.list.currentRow() + 1, n - 1))
        if self.list.currentItem():
            self.list.scrollToItem(self.list.currentItem())

    def select_prev(self):
        n = self.list.count()
        if n == 0: return
        self.list.setCurrentRow(max(self.list.currentRow() - 1, 0))
        if self.list.currentItem():
            self.list.scrollToItem(self.list.currentItem())

    def current_item(self):
        return self.list.currentItem()

    def confirm_current(self):
        item = self.current_item()
        if item:
            self._on_select(item)

    def apply_theme(self, dark: bool):
        if dark:
            self.setStyleSheet("""
                QWidget     { background:#2b2b2b; border:1px solid #555; border-radius:3px; }
                QListWidget { background:#2b2b2b; color:#e8e8e8; border:none; font-size:13px; outline:0; }
                QListWidget::item          { padding:6px 12px; color:#e8e8e8; border-bottom:1px solid #3a3a3a; }
                QListWidget::item:hover    { background:#3a5278; color:#fff; }
                QListWidget::item:selected { background:#1565c0; color:#fff; }
                QScrollBar:vertical        { background:#3a3a3a; width:12px; }
                QScrollBar::handle:vertical{ background:#666; border-radius:4px; min-height:24px; }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
                QScrollBar:horizontal      { background:#3a3a3a; height:12px; }
                QScrollBar::handle:horizontal { background:#666; border-radius:4px; }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
            """)
        else:
            self.setStyleSheet("""
                QWidget     { background:#fff; border:1px solid #90caf9; border-radius:3px; }
                QListWidget { background:#fff; color:#1a1a2e; border:none; font-size:13px; outline:0; }
                QListWidget::item          { padding:6px 12px; color:#1a1a2e; border-bottom:1px solid #eee; }
                QListWidget::item:hover    { background:#e3f2fd; color:#0d47a1; }
                QListWidget::item:selected { background:#1565c0; color:#fff; }
                QScrollBar:vertical        { background:#f0f0f0; width:12px; }
                QScrollBar::handle:vertical{ background:#bbb; border-radius:4px; min-height:24px; }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
                QScrollBar:horizontal      { background:#f0f0f0; height:12px; }
                QScrollBar::handle:horizontal { background:#bbb; border-radius:4px; }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
            """)


# ─────────────────────────────────────────────────────────────────────────────
#  Delegate
# ─────────────────────────────────────────────────────────────────────────────

class AutocompleteDelegate(QStyledItemDelegate):
    def __init__(self, ref_getter, theme_getter=None, table=None, parent=None):
        super().__init__(parent)
        self._get_ref   = ref_getter
        self._get_theme = theme_getter
        self._table     = table

        self._popup      : AutocompletePopup | None = None
        self._editor     : QLineEdit | None         = None
        self._cur_idx    = None
        self._model      = None       # modelo guardado al crear editor
        self._no_search  : bool = False
        # Flag: indica si ya escribimos en el modelo directamente (clic)
        # para que setModelData no sobreescriba con texto vacío
        self._committed  : bool = False

    # ── Ciclo de vida ──────────────────────────────────────────────────────────

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setPlaceholderText("Escribí para buscar…")
        self._editor    = editor
        self._cur_idx   = index
        self._model     = index.model()   # guardar referencia al modelo aquí
        self._committed = False

        dark = bool(self._get_theme and self._get_theme() == "dark")
        popup = AutocompletePopup(on_select=self._on_selected)
        popup.apply_theme(dark)
        self._popup = popup

        editor.textChanged.connect(self._search)
        editor.installEventFilter(self)
        return editor

    def setEditorData(self, editor, index):
        val = index.data(Qt.EditRole) or ""
        self._no_search = True
        editor.setText(val)
        editor.selectAll()
        self._no_search = False

    def setModelData(self, editor, model, index):
        # Si ya escribimos directamente en el modelo (vía clic), no hacer nada
        if self._committed:
            return
        # Caso Enter: guardar el texto actual del editor
        model.setData(index, editor.text(), Qt.EditRole)

    def destroyEditor(self, editor, index):
        if self._popup:
            self._popup.hide()
            self._popup.deleteLater()
            self._popup = None
        self._editor = None
        super().destroyEditor(editor, index)

    # ── Búsqueda ──────────────────────────────────────────────────────────────

    @staticmethod
    def _multi_match(query: str, record: dict, search_cols: list) -> bool:
        terms = [t.lower() for t in query.split() if t]
        if not terms:
            return False
        cols = search_cols if search_cols else list(record.keys())
        haystack = " ".join(str(record.get(c, "")) for c in cols).lower()
        return all(t in haystack for t in terms)

    def _search(self, text: str):
        if self._no_search:
            return
        self._committed = False

        query = text.strip()
        popup = self._popup
        if not query or popup is None:
            if popup:
                popup.hide()
            return

        result = self._get_ref()
        if len(result) == 4:
            records, id_col, search_cols, copy_cols = result
        else:
            records, id_col = result[0], result[1]
            search_cols, copy_cols = [], []

        if not records:
            return

        matches = []
        for rec in records:
            if self._multi_match(query, rec, search_cols):
                id_val  = str(rec.get(id_col, ""))
                display = "  ".join(
                    str(rec.get(c, "")) for c in (search_cols or list(rec.keys()))
                    if rec.get(c, "")
                )
                label = "  |  ".join(str(v) for v in rec.values())
                extra = {c: str(rec.get(c, "")) for c in copy_cols}
                matches.append((display, id_val, label, extra))

        popup.list.clear()
        for display, id_val, label, extra in matches[:200]:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, (display, id_val, extra))
            popup.list.addItem(item)

        if not matches:
            popup.hide()
            return

        dark = bool(self._get_theme and self._get_theme() == "dark")
        popup.apply_theme(dark)
        if self._editor:
            popup.show_below(self._editor)
            self._editor.setFocus()

    # ── Selección ─────────────────────────────────────────────────────────────

    def _on_selected(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole)
        if data is None:
            return
        display, id_val, extra = data

        # ── ESCRITURA DIRECTA EN EL MODELO ──────────────────────────────────
        # Hacemos esto AQUÍ, antes de cualquier timer o ciclo de editor,
        # porque el editor puede destruirse en cualquier momento tras el clic.
        if self._model is not None and self._cur_idx is not None:
            row      = self._cur_idx.row()
            match_col = self._cur_idx.column()
            last_col  = self._model.columnCount() - 1

            # 1. Columna Coincidencia (la celda que se está editando)
            self._model.setData(
                self._model.index(row, match_col), display, Qt.EditRole
            )
            # 2. Columna ID Referencia (última columna)
            self._model.setData(
                self._model.index(row, last_col), id_val, Qt.EditRole
            )
            # 3. Columnas extra (copy_cols)
            self._write_extra(extra)

        self._committed = True  # decirle a setModelData que no sobreescriba

        # Actualizar el editor visualmente (puede que ya esté destruido, sin problema)
        if self._editor:
            self._no_search = True
            self._editor.setText(display)
            self._no_search = False

        if self._popup:
            self._popup.hide()

        # Cerrar editor y avanzar
        saved = self._cur_idx
        if self._editor:
            self._editor.setFocus()
        QTimer.singleShot(20, lambda: self._commit_and_advance(saved))

    def _write_extra(self, extra: dict):
        if not extra or self._model is None or self._cur_idx is None:
            return
        if not hasattr(self._model, "get_headers"):
            return
        row     = self._cur_idx.row()
        headers = self._model.get_headers()
        for col_name, value in extra.items():
            if col_name in headers:
                self._model.setData(
                    self._model.index(row, headers.index(col_name)),
                    value, Qt.EditRole
                )
            elif hasattr(self._model, "add_column"):
                self._model.add_column(col_name)
                headers = self._model.get_headers()
                self._model.setData(
                    self._model.index(row, headers.index(col_name)),
                    value, Qt.EditRole
                )

    # ── Confirmar + avanzar ───────────────────────────────────────────────────

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

    # ── Event filter ──────────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is not self._editor or event.type() != QEvent.KeyPress:
            return super().eventFilter(obj, event)

        key     = event.key()
        popup   = self._popup
        visible = popup is not None and popup.isVisible()

        if key == Qt.Key_Down:
            if visible:
                if popup.current_item() is None:
                    popup.list.setCurrentRow(0)
                else:
                    popup.select_next()
            return True

        if key == Qt.Key_Up:
            if visible:
                popup.select_prev()
            return True

        if key in (Qt.Key_Return, Qt.Key_Enter):
            if visible:
                if popup.current_item() is None and popup.list.count() > 0:
                    popup.list.setCurrentRow(0)
                if popup.current_item():
                    popup.confirm_current()
                    return True
            saved = self._cur_idx
            QTimer.singleShot(20, lambda: self._commit_and_advance(saved))
            return True

        if key == Qt.Key_Escape:
            if visible:
                popup.hide()
                return True

        if key == Qt.Key_Tab and visible:
            popup.hide()

        return super().eventFilter(obj, event)
