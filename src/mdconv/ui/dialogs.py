"""Informative dialogs: About Dialog and Supported Formats Dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mdconv import __version__
from mdconv.engine import supported_conversions
from mdconv.tools import ToolMissingError, find_tool


def is_pandoc_available() -> bool:
    try:
        find_tool("pandoc")
        return True
    except (ToolMissingError, Exception):  # noqa: BLE001
        return False


def is_typst_available() -> bool:
    try:
        find_tool("typst")
        return True
    except (ToolMissingError, Exception):  # noqa: BLE001
        return False


import importlib.util


def is_docling_available() -> bool:
    try:
        return importlib.util.find_spec("docling") is not None
    except Exception:  # noqa: BLE001
        return False


class FormatsDialog(QDialog):
    """Dialog showing supported conversion pairs and external tool statuses."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Unterstützte Formate & Werkzeuge")
        self.resize(640, 480)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info_label = QLabel(
            "<b>Konvertierungsübersicht & Status der externen Werkzeuge:</b>"
        )
        layout.addWidget(info_label)

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Von", "Nach", "Technologie", "Status"])
        table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        table.setAlternatingRowColors(True)

        pandoc_ok = is_pandoc_available()
        typst_ok = is_typst_available()
        docling_ok = is_docling_available()

        tech_map = {
            ("md", "docx"): ("Pandoc", pandoc_ok),
            ("md", "html"): ("Pandoc", pandoc_ok),
            ("md", "pdf"): ("Pandoc + Typst", pandoc_ok and typst_ok),
            ("md", "xlsx"): ("Python (openpyxl)", True),
            ("md", "csv"): ("Python (csv)", True),
            ("docx", "md"): ("Pandoc", pandoc_ok),
            ("html", "md"): ("Pandoc", pandoc_ok),
            ("xlsx", "md"): ("Python (openpyxl)", True),
            ("csv", "md"): ("Python (csv)", True),
            ("pdf", "md"): ("Docling (ML/OCR)", docling_ok),
        }

        conversions = supported_conversions()
        for src, dst in conversions:
            row = table.rowCount()
            table.insertRow(row)

            tech_info, is_available = tech_map.get((src, dst), ("Intern", True))

            src_item = QTableWidgetItem(src.upper())
            src_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            dst_item = QTableWidgetItem(dst.upper())
            dst_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            tech_item = QTableWidgetItem(tech_info)

            status_text = "Verfügbar ✓" if is_available else "Werkzeug fehlt ✗"
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_color = "#10b981" if is_available else "#ef4444"
            status_item.setForeground(QColor(status_color))

            for item in (src_item, dst_item, tech_item, status_item):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            table.setItem(row, 0, src_item)
            table.setItem(row, 1, dst_item)
            table.setItem(row, 2, tech_item)
            table.setItem(row, 3, status_item)

        layout.addWidget(table)

        tools_status_box = QLabel(
            f"<p><b>Status der externen Werkzeuge:</b><br>"
            f"• <b>Pandoc:</b> {'Bereit (integriert)' if pandoc_ok else 'Nicht gefunden (bitte pypandoc-binary oder PATH prüfen)'}<br>"
            f"• <b>Typst (für MD → PDF):</b> {'Gefunden' if typst_ok else 'Nicht gefunden (typst.exe in vendor/bin oder PATH legen)'}<br>"
            f"• <b>Docling (für PDF → MD):</b> {'Installiert' if docling_ok else 'Optional (uv sync --extra pdf)'}</p>"
        )
        tools_status_box.setStyleSheet(
            "background-color: #24283b; padding: 8px; border-radius: 6px;"
        )
        layout.addWidget(tools_status_box)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class AboutDialog(QDialog):
    """About dialog showing application description and credentials."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Über py-md-converter")
        self.resize(460, 280)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel(f"<h2>py-md-converter v{__version__}</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "<p align='center'>Moderner All-in-One Dokumenten- und Tabellen-Konverter.</p>"
            "<p align='center'>"
            "Konvertiert <b>Markdown</b> in <b>DOCX, HTML, PDF, XLSX, CSV</b> – und zurück.<br>"
            "Mit Stapelverarbeitung, Drag & Drop und nativer PySide6 Desktop-Oberfläche."
            "</p>"
            "<hr>"
            "<p align='center' style='color: #7982a9; font-size: 11px;'>"
            "Entwickelt mit Python, PySide6, Pandoc, Typst & OpenPyXL.<br>"
            "Data-AL GmbH & Carasent"
            "</p>"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
