"""
CSVMapper - Main entry point
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from ui_main import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CSVMapper")
    app.setOrganizationName("CSVMapper")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
