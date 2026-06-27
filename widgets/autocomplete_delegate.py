"""
widgets/autocomplete_delegate.py — Popup de autocompletado.

Fixes en esta versión:
  - _on_selected escribe el display en el editor Y lo guarda en setModelData.
  - _write_id usa setData directamente en el modelo base (no el proxy).
  - Búsqueda multi-término sobre los campos seleccionados en ref_tab (search_cols).
  - Al seleccionar, copia también las copy_cols al modelo de trabajo.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QStyledItemDelegate, QLineEdit, QListWidget, QListWidgetItem,
    QWidget, QVBoxLayout, QHBoxLayout, QSizeGrip, QAbstractItemView,
    QApplication,
)
from PySide6.QtCore import Qt, QPoint, QRect, QTimer, QEvent


# ─────────────────────────────────────────────────────────────────────────────
#  Lista interna
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
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        super().wheelEvent(event)
        event.accept()


# ─────────────────────────────────────────────────────────────────────────────
#  Popup
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
        self.setMinimumSize(400, 140)

        screen_w = QApplication.primaryScreen().availableGeometry().width()
        self.resize(max(700, screen_w // 2), 300)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 4)
        lay.setSpacing(0)

        self.list = _ClickList(self._on_select)
        lay.addWidget(self.list)

        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 2, 0)
        grip_row.addStretch()
        grip_row.addWidget(QSizeGrip(self))
        lay.addLayout(grip_row)

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
        self.list.scrollToItem(self.list.currentItem())

    def select_prev(self):
        n = self.list.count()
        if n == 0: return
        self.list.setCurrentRow(max(self.list.currentRow() - 1, 0))
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
                QWidget     { background:#2b2b2b; border:1px solid #555; border-radius:4px; }
                QListWidget { background:#2b2b2b; color:#e8e8e8; border:none;
                              font-size:13px; outline:0; }
                QListWidget::item          { padding:5px 10px; color:#e8e8e8;
                                             border-bottom:1px solid #3a3a3a; }
                QListWidget::item:hover    { background:#3a5278; color:#fff; }
                QListWidget::item:selected { background:#1565c0; color:#fff; }
                QScrollBar:vertical        { background:#3a3a3a; width:12px; }
                QScrollBar::handle:vertical{ background:#666; border-radius:4px; min-height:20px; }
                QScrollBar:horizontal      { background:#3a3a3a; height:12px; }
                QScrollBar::handle:horizontal{ background:#666; border-radius:4px; }
                QSizeGrip { background:transparent; width:14px; height:14px; }
            """)
        else:
            self.setStyleSheet("""
                QWidget     { background:#fff; border:1px solid #90caf9; border-radius:4px; }
                QListWidget { background:#fff; color:#1a1a2e; border:none;
                              font-size:13px; outline:0; }
                QListWidget::item          { padding:5px 10px; color:#1a1a2e;
                                             border-bottom:1px solid #eee; }
                QListWidget::item:hover    { background:#e3f2fd; color:#0d47a1; }
                QListWidget::item:selected { background:#1565c0; color:#fff; }
                QScrollBar:vertical        { background:#f0f0f0; width:12px; }
                QScrollBar::handle:vertical{ background:#bbb; border-radius:4px; min-height:20px; }
                QScrollBar:horizontal      { background:#f0f0f0; height:12px; }
                QScrollBar::handle:horizontal{ background:#bbb; border-radius:4px; }
                QSizeGrip { background:transparent; width:14px; height:14px; }
            """)


# ─────────────────────────────────────────────────────────────────────────────
#  Delegate
# ─────────────────────────────────────────────────────────────────────────────

class AutocompleteDelegate(QStyledItemDelegate):
    def __init__(self, ref_getter, theme_getter=None, table=None, parent=None):
        super().__init__(parent)
        self._get_ref   = ref_getter    # → (records, id_col, search_cols, copy_cols)
        self._get_theme = theme_getter
        self._table     = table

        self._popup        : AutocompletePopup | None = None
        self._editor       : QLineEdit | None         = None
        self._cur_idx      = None
        self._model        = None
        self._sel_display  : str | None = None   # texto que va en COL_MATCH
        self._sel_id       : str | None = None   # ID que va en COL_ID
        self._sel_extra    : dict       = {}      # col → valor para columnas extra
        self._no_search    : bool       = False

    # ── Ciclo de vida ──────────────────────────────────────────────────────────

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setPlaceholderText("Escribí para buscar…")
        self._editor     = editor
        self._cur_idx    = index
        self._model      = index.model()
        self._sel_display = None
        self._sel_id      = None
        self._sel_extra   = {}

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
        # Escribir el texto de coincidencia (display) en la celda
        val = self._sel_display if self._sel_display is not None else editor.text()
        model.setData(index, val, Qt.EditRole)

    def destroyEditor(self, editor, index):
        if self._popup:
            self._popup.hide()
            self._popup.deleteLater()
            self._popup = None
        self._editor = None
        super().destroyEditor(editor, index)

    # ── Búsqueda ──────────────────────────────────────────────────────────────

    @staticmethod
    def _multi_match(query: str, record: dict, search_cols: list[str]) -> bool:
        """AND entre términos, buscando solo en search_cols."""
        terms = [t.lower() for t in query.split() if t]
        if not terms:
            return False
        # Si no hay columnas seleccionadas, buscar en todas
        cols = search_cols if search_cols else list(record.keys())
        haystack = " ".join(str(record.get(c, "")) for c in cols).lower()
        return all(t in haystack for t in terms)

    def _search(self, text: str):
        if self._no_search:
            return
        self._sel_display = None
        self._sel_id      = None
        self._sel_extra   = {}

        query = text.strip()
        popup = self._popup
        if not query or popup is None:
            if popup:
                popup.hide()
            return

        result = self._get_ref()
        # Soporte para ambas firmas: 3 valores (legacy) y 4 valores (nuevo)
        if len(result) == 4:
            records, id_col, search_cols, copy_cols = result
        else:
            records, id_col, disp_col = result
            search_cols = []
            copy_cols   = []

        if not records:
            return

        matches = []
        for rec in records:
            if self._multi_match(query, rec, search_cols):
                id_val  = str(rec.get(id_col, ""))
                # El texto que se escribe en COL_MATCH = valores de search_cols unidos
                if search_cols:
                    display = "  ".join(str(rec.get(c, "")) for c in search_cols if rec.get(c, ""))
                else:
                    display = str(rec.get(id_col, ""))
                label   = "  |  ".join(str(v) for v in rec.values())
                # Extra: valores de copy_cols
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

        self._sel_display = display
        self._sel_id      = id_val
        self._sel_extra   = extra

        # 1. Escribir display en el editor (COL_MATCH)
        if self._editor:
            self._no_search = True
            self._editor.setText(display)
            self._no_search = False

        # 2. Escribir ID en COL_ID (última columna)
        self._write_id(id_val)

        # 3. Escribir columnas extra en el modelo de trabajo
        self._write_extra(extra)

        if self._popup:
            self._popup.hide()

        saved = self._cur_idx
        if self._editor:
            self._editor.setFocus()
        QTimer.singleShot(20, lambda: self._commit_and_advance(saved))

    def _write_id(self, id_val: str):
        """Escribe el ID en la última columna de la fila actual."""
        if self._cur_idx is None or self._model is None:
            return
        row     = self._cur_idx.row()
        last    = self._model.columnCount() - 1
        self._model.setData(self._model.index(row, last), id_val, Qt.EditRole)

    def _write_extra(self, extra: dict):
        """
        Escribe los valores de copy_cols en columnas del modelo de trabajo.
        Busca la columna por nombre en los headers del modelo.
        Si la columna no existe, la crea automáticamente.
        """
        if not extra or self._model is None or self._cur_idx is None:
            return
        row = self._cur_idx.row()
        # Obtener headers del modelo (que tiene get_headers())
        if hasattr(self._model, "get_headers"):
            headers = self._model.get_headers()
        else:
            return
        for col_name, value in extra.items():
            if col_name in headers:
                col_idx = headers.index(col_name)
                self._model.setData(self._model.index(row, col_idx), value, Qt.EditRole)
            else:
                # Agregar la columna automáticamente si no existe
                if hasattr(self._model, "add_column"):
                    self._model.add_column(col_name)
                    headers = self._model.get_headers()
                    col_idx = headers.index(col_name)
                    self._model.setData(self._model.index(row, col_idx), value, Qt.EditRole)

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
