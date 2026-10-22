import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel
from PySide6.QtCore import Qt


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("py-md-converter")
        self.resize(800, 600)
        label = QLabel("Hallo aus py-md-converter!", alignment=Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(label)


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()