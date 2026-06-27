"""
theme.py - Paletas de color para tema claro y oscuro.
"""

LIGHT = """
QMainWindow, QWidget { background: #f0f2f5; color: #1a1a2e; }
QTabWidget::pane { border: 1px solid #d0d3d8; background: #ffffff; border-radius: 4px; }
QTabBar::tab {
    padding: 8px 22px; font-size: 13px; background: #e4e7ec;
    border: 1px solid #c9cdd4; border-bottom: none;
    border-top-left-radius: 4px; border-top-right-radius: 4px; color: #555;
}
QTabBar::tab:selected { background: #ffffff; color: #1a1a2e; font-weight: bold; }
QTabBar::tab:hover   { background: #f0f2f5; }

QPushButton {
    background: #3f51b5; color: #ffffff; border: none;
    border-radius: 4px; padding: 5px 14px; font-size: 12px;
}
QPushButton:hover   { background: #5c6bc0; }
QPushButton:pressed { background: #303f9f; }
QPushButton#btn_close   { background: #e53935; }
QPushButton#btn_close:hover { background: #ef5350; }
QPushButton#btn_export  { background: #2e7d32; }
QPushButton#btn_export:hover { background: #388e3c; }
QPushButton#btn_theme   { background: #546e7a; }
QPushButton#btn_theme:hover { background: #607d8b; }

QTableView {
    gridline-color: #e0e3e8; font-size: 12px;
    background: #ffffff; color: #1a1a2e;
    selection-background-color: #bbdefb; selection-color: #000000;
    alternate-background-color: #f5f7fa;
}
QTableView QHeaderView::section {
    background: #3f51b5; color: #ffffff;
    padding: 5px 8px; border: none; font-size: 12px; font-weight: bold;
}
QHeaderView { background: #3f51b5; }

QComboBox {
    border: 1px solid #bbb; border-radius: 3px;
    padding: 4px 8px; font-size: 12px;
    background: #ffffff; color: #1a1a2e;
}
QComboBox QAbstractItemView { background: #ffffff; color: #1a1a2e; selection-background-color: #bbdefb; }

QLineEdit {
    border: 1px solid #90caf9; border-radius: 3px;
    padding: 4px; font-size: 12px;
    background: #ffffff; color: #1a1a2e;
}
QScrollBar:vertical { background: #f0f2f5; width: 10px; }
QScrollBar::handle:vertical { background: #bbb; border-radius: 5px; }
QStatusBar { background: #3f51b5; color: #ffffff; font-size: 11px; }
QLabel { font-size: 12px; color: #1a1a2e; }
QFrame { color: #1a1a2e; }
"""

DARK = """
QMainWindow, QWidget { background: #1e1e2e; color: #e8e8f0; }
QTabWidget::pane { border: 1px solid #444; background: #252535; border-radius: 4px; }
QTabBar::tab {
    padding: 8px 22px; font-size: 13px; background: #2a2a3e;
    border: 1px solid #444; border-bottom: none;
    border-top-left-radius: 4px; border-top-right-radius: 4px; color: #aaaacc;
}
QTabBar::tab:selected { background: #252535; color: #e8e8f0; font-weight: bold; }
QTabBar::tab:hover   { background: #303050; }

QPushButton {
    background: #5c6bc0; color: #ffffff; border: none;
    border-radius: 4px; padding: 5px 14px; font-size: 12px;
}
QPushButton:hover   { background: #7986cb; }
QPushButton:pressed { background: #3949ab; }
QPushButton#btn_close   { background: #c62828; }
QPushButton#btn_close:hover { background: #ef5350; }
QPushButton#btn_export  { background: #1b5e20; }
QPushButton#btn_export:hover { background: #2e7d32; }
QPushButton#btn_theme   { background: #37474f; }
QPushButton#btn_theme:hover { background: #546e7a; }

QTableView {
    gridline-color: #3a3a5a; font-size: 12px;
    background: #252535; color: #e8e8f0;
    selection-background-color: #1565c0; selection-color: #ffffff;
    alternate-background-color: #2a2a42;
}
QTableView QHeaderView::section {
    background: #3949ab; color: #ffffff;
    padding: 5px 8px; border: none; font-size: 12px; font-weight: bold;
}
QHeaderView { background: #3949ab; }

QComboBox {
    border: 1px solid #555; border-radius: 3px;
    padding: 4px 8px; font-size: 12px;
    background: #2a2a3e; color: #e8e8f0;
}
QComboBox QAbstractItemView { background: #2a2a3e; color: #e8e8f0; selection-background-color: #1565c0; }

QLineEdit {
    border: 1px solid #5c6bc0; border-radius: 3px;
    padding: 4px; font-size: 12px;
    background: #2a2a3e; color: #e8e8f0;
}
QScrollBar:vertical { background: #2a2a3e; width: 10px; }
QScrollBar::handle:vertical { background: #555; border-radius: 5px; }
QStatusBar { background: #12122a; color: #aaaacc; font-size: 11px; }
QLabel { font-size: 12px; color: #e8e8f0; }
QFrame { color: #e8e8f0; }
"""

THEMES = {"light": LIGHT, "dark": DARK}
