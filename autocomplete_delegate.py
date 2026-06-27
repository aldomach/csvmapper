"""
autocomplete_delegate.py
Custom QStyledItemDelegate that shows a live autocomplete popup.
The popup fuzzy-searches every word in every reference record.
"""
from PySide6.QtWidgets import (
    QStyledItemDelegate, QLineEdit, QListWidget, QListWidgetItem,
    QFrame, QApplication
)
from PySide6.QtCore import Qt, QEvent, QPoint, QTimer
from PySide6.QtGui import QKeyEvent


class AutocompletePopup(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setFrameShape(QFrame.StyledPanel)
        self.setMaximumHeight(250)
        from PySide6.QtWidgets import QVBoxLayout
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        lay.addWidget(self.list)
        self.setMinimumWidth(350)

    def show_at(self, global_pos: QPoint):
        self.move(global_pos)
        self.show()


class AutocompleteDelegate(QStyledItemDelegate):
    """
    Used for the penultimate column (match column).
    On cell edit: shows a popup with records from the reference tab.
    On selection (Enter / click): writes the display text in this column
      and the ID in the last column.
    """

    def __init__(self, ref_tab_getter, parent=None):
        super().__init__(parent)
        self._get_ref = ref_tab_getter   # callable → (records, id_col, disp_col)
        self._popup: AutocompletePopup | None = None
        self._editor: QLineEdit | None = None
        self._current_index = None       # QModelIndex being edited
        self._model = None

    # ── Editor lifecycle ───────────────────────────────────────────────────────

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setPlaceholderText("Escribí para buscar…")
        self._editor = editor
        self._current_index = index
        self._model = index.model()

        popup = AutocompletePopup(parent.window())
        self._popup = popup
        popup.list.itemActivated.connect(self._on_item_activated)

        editor.textChanged.connect(self._on_text_changed)
        editor.installEventFilter(self)
        return editor

    def setEditorData(self, editor, index):
        val = index.data(Qt.EditRole) or ""
        editor.setText(val)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.text(), Qt.EditRole)

    def destroyEditor(self, editor, index):
        if self._popup:
            self._popup.hide()
            self._popup = None
        super().destroyEditor(editor, index)

    # ── Autocomplete logic ─────────────────────────────────────────────────────

    def _on_text_changed(self, text: str):
        text = text.strip().lower()
        if not text or not self._popup:
            if self._popup:
                self._popup.hide()
            return

        records, id_col, disp_col = self._get_ref()
        if not records:
            return

        matches = []
        for rec in records:
            haystack = " ".join(str(v) for v in rec.values()).lower()
            if text in haystack:
                display = rec.get(disp_col, "")
                id_val  = rec.get(id_col, "")
                matches.append((display, id_val, rec))

        self._popup.list.clear()
        for display, id_val, rec in matches[:60]:
            item = QListWidgetItem(f"{display}  [{id_val}]")
            item.setData(Qt.UserRole, (display, id_val))
            self._popup.list.addItem(item)

        if matches:
            editor = self._editor
            if editor:
                gp = editor.mapToGlobal(QPoint(0, editor.height()))
                self._popup.setMinimumWidth(max(350, editor.width()))
                self._popup.show_at(gp)
        else:
            self._popup.hide()

    def _on_item_activated(self, item: QListWidgetItem):
        display, id_val = item.data(Qt.UserRole)
        if self._editor:
            self._editor.setText(display)
        self._write_id(id_val)
        if self._popup:
            self._popup.hide()
        # Commit and close editor
        if self._editor:
            QTimer.singleShot(0, lambda: self._commit_and_close())

    def _commit_and_close(self):
        if self._editor:
            self.commitData.emit(self._editor)
            self.closeEditor.emit(self._editor, QStyledItemDelegate.NoHint)

    def _write_id(self, id_val: str):
        """Write the ID value into the LAST column of the same row."""
        if self._current_index is None or self._model is None:
            return
        row = self._current_index.row()
        last_col = self._model.columnCount() - 1
        self._model.setData(self._model.index(row, last_col), id_val, Qt.EditRole)

    # ── Event filter (keyboard nav in popup) ──────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self._editor and isinstance(event, QKeyEvent):
            key = event.key()
            if key == Qt.Key_Down and self._popup and self._popup.isVisible():
                self._popup.list.setFocus()
                self._popup.list.setCurrentRow(0)
                return True
            if key == Qt.Key_Escape and self._popup:
                self._popup.hide()
                return False
            if key in (Qt.Key_Return, Qt.Key_Enter):
                if self._popup and self._popup.isVisible():
                    current = self._popup.list.currentItem()
                    if current:
                        self._on_item_activated(current)
                        return True
        return super().eventFilter(obj, event)
