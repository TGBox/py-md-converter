"""Theme definitions and stylesheet management for py-md-converter."""

from __future__ import annotations

from typing import Literal

ThemeMode = Literal["dark", "light"]

DARK_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #1a1b26;
    color: #c0caf5;
    font-family: "Segoe UI", Roboto, -apple-system, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #c0caf5;
    font-family: "Segoe UI", Roboto, -apple-system, sans-serif;
    font-size: 13px;
}

QGroupBox {
    border: 1px solid #2f354a;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 12px;
    font-weight: 600;
    color: #7aa2f7;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    background-color: #1a1b26;
}

QLabel {
    color: #c0caf5;
}

QLabel#mutedLabel {
    color: #7982a9;
    font-size: 11px;
}

QLabel#headerTitle {
    font-size: 18px;
    font-weight: bold;
    color: #bb9af7;
}

QLineEdit, QComboBox, QSpinBox {
    background-color: #24283b;
    border: 1px solid #3b4261;
    border-radius: 6px;
    padding: 6px 10px;
    color: #c0caf5;
    selection-background-color: #7aa2f7;
    selection-color: #1a1b26;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #7aa2f7;
    background-color: #292e42;
}

QLineEdit:disabled, QComboBox:disabled {
    background-color: #1f2335;
    color: #565f89;
    border-color: #292e42;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #3b4261;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QComboBox QAbstractItemView {
    background-color: #24283b;
    border: 1px solid #3b4261;
    border-radius: 6px;
    selection-background-color: #3d59a1;
    selection-color: #ffffff;
    color: #c0caf5;
    padding: 4px;
}

QPushButton {
    background-color: #24283b;
    border: 1px solid #3b4261;
    border-radius: 6px;
    padding: 7px 14px;
    color: #c0caf5;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #2f354a;
    border-color: #7aa2f7;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #1f2335;
}

QPushButton:disabled {
    background-color: #1f2335;
    border-color: #292e42;
    color: #565f89;
}

QPushButton#primaryButton {
    background-color: #7aa2f7;
    color: #15161e;
    border: none;
    font-weight: bold;
    padding: 8px 18px;
}

QPushButton#primaryButton:hover {
    background-color: #89b4fa;
}

QPushButton#primaryButton:pressed {
    background-color: #6187db;
}

QPushButton#primaryButton:disabled {
    background-color: #3b4261;
    color: #7982a9;
}

QPushButton#dangerButton {
    background-color: #f7768e;
    color: #15161e;
    border: none;
    font-weight: bold;
    padding: 8px 16px;
}

QPushButton#dangerButton:hover {
    background-color: #ff8b9f;
}

QPushButton#dangerButton:pressed {
    background-color: #db5971;
}

QCheckBox {
    spacing: 8px;
    color: #c0caf5;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #3b4261;
    border-radius: 4px;
    background-color: #24283b;
}

QCheckBox::indicator:hover {
    border-color: #7aa2f7;
}

QCheckBox::indicator:checked {
    background-color: #7aa2f7;
    border-color: #7aa2f7;
}

QTableWidget {
    background-color: #1f2335;
    alternate-background-color: #24283b;
    border: 1px solid #2f354a;
    border-radius: 8px;
    gridline-color: #292e42;
    color: #c0caf5;
    selection-background-color: #3d59a1;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #24283b;
    color: #a9b1d6;
    padding: 6px 10px;
    border: none;
    border-bottom: 2px solid #3b4261;
    font-weight: 600;
}

QTextEdit {
    background-color: #16161e;
    color: #a9b1d6;
    border: 1px solid #2f354a;
    border-radius: 8px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    padding: 6px;
}

QProgressBar {
    border: 1px solid #3b4261;
    border-radius: 6px;
    text-align: center;
    background-color: #1f2335;
    color: #ffffff;
    font-weight: bold;
    height: 20px;
}

QProgressBar::chunk {
    background-color: #7aa2f7;
    border-radius: 5px;
}

QMenuBar {
    background-color: #1a1b26;
    color: #a9b1d6;
    border-bottom: 1px solid #2f354a;
}

QMenuBar::item {
    background: transparent;
    padding: 6px 12px;
}

QMenuBar::item:selected {
    background-color: #24283b;
    color: #ffffff;
    border-radius: 4px;
}

QMenu {
    background-color: #24283b;
    color: #c0caf5;
    border: 1px solid #3b4261;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #7aa2f7;
    color: #15161e;
}

QMenu::separator {
    height: 1px;
    background-color: #3b4261;
    margin: 4px 6px;
}

QStatusBar {
    background-color: #16161e;
    color: #7982a9;
    border-top: 1px solid #2f354a;
}

QScrollBar:vertical {
    border: none;
    background-color: #1a1b26;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #3b4261;
    border-radius: 5px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #7aa2f7;
}

QScrollBar:horizontal {
    border: none;
    background-color: #1a1b26;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #3b4261;
    border-radius: 5px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #7aa2f7;
}

QScrollBar::add-line, QScrollBar::sub-line {
    width: 0px;
    height: 0px;
}
"""

LIGHT_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #f8fafc;
    color: #1e293b;
    font-family: "Segoe UI", Roboto, -apple-system, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #1e293b;
    font-family: "Segoe UI", Roboto, -apple-system, sans-serif;
    font-size: 13px;
}

QGroupBox {
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 12px;
    font-weight: 600;
    color: #2563eb;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    background-color: #f8fafc;
}

QLabel {
    color: #1e293b;
}

QLabel#mutedLabel {
    color: #64748b;
    font-size: 11px;
}

QLabel#headerTitle {
    font-size: 18px;
    font-weight: bold;
    color: #1e3a8a;
}

QLineEdit, QComboBox, QSpinBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 10px;
    color: #1e293b;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #2563eb;
    background-color: #ffffff;
}

QLineEdit:disabled, QComboBox:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border-color: #e2e8f0;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #cbd5e1;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    color: #1e293b;
    padding: 4px;
}

QPushButton {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 7px 14px;
    color: #1e293b;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #f1f5f9;
    border-color: #2563eb;
    color: #1d4ed8;
}

QPushButton:pressed {
    background-color: #e2e8f0;
}

QPushButton:disabled {
    background-color: #f1f5f9;
    border-color: #e2e8f0;
    color: #94a3b8;
}

QPushButton#primaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    font-weight: bold;
    padding: 8px 18px;
}

QPushButton#primaryButton:hover {
    background-color: #1d4ed8;
}

QPushButton#primaryButton:pressed {
    background-color: #1e40af;
}

QPushButton#primaryButton:disabled {
    background-color: #94a3b8;
    color: #f8fafc;
}

QPushButton#dangerButton {
    background-color: #ef4444;
    color: #ffffff;
    border: none;
    font-weight: bold;
    padding: 8px 16px;
}

QPushButton#dangerButton:hover {
    background-color: #dc2626;
}

QPushButton#dangerButton:pressed {
    background-color: #b91c1c;
}

QCheckBox {
    spacing: 8px;
    color: #1e293b;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    background-color: #ffffff;
}

QCheckBox::indicator:hover {
    border-color: #2563eb;
}

QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #2563eb;
}

QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    gridline-color: #e2e8f0;
    color: #1e293b;
    selection-background-color: #dbeafe;
    selection-color: #1e3a8a;
}

QHeaderView::section {
    background-color: #f1f5f9;
    color: #475569;
    padding: 6px 10px;
    border: none;
    border-bottom: 2px solid #cbd5e1;
    font-weight: 600;
}

QTextEdit {
    background-color: #f8fafc;
    color: #334155;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    padding: 6px;
}

QProgressBar {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    text-align: center;
    background-color: #e2e8f0;
    color: #1e293b;
    font-weight: bold;
    height: 20px;
}

QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 5px;
}

QMenuBar {
    background-color: #ffffff;
    color: #334155;
    border-bottom: 1px solid #e2e8f0;
}

QMenuBar::item {
    background: transparent;
    padding: 6px 12px;
}

QMenuBar::item:selected {
    background-color: #f1f5f9;
    color: #1e293b;
    border-radius: 4px;
}

QMenu {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background-color: #e2e8f0;
    margin: 4px 6px;
}

QStatusBar {
    background-color: #f1f5f9;
    color: #64748b;
    border-top: 1px solid #e2e8f0;
}

QScrollBar:vertical {
    border: none;
    background-color: #f1f5f9;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #cbd5e1;
    border-radius: 5px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #94a3b8;
}

QScrollBar:horizontal {
    border: none;
    background-color: #f1f5f9;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #cbd5e1;
    border-radius: 5px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #94a3b8;
}

QScrollBar::add-line, QScrollBar::sub-line {
    width: 0px;
    height: 0px;
}
"""


def get_stylesheet(theme: ThemeMode) -> str:
    """Returns the CSS stylesheet for the requested theme."""
    return DARK_STYLESHEET if theme == "dark" else LIGHT_STYLESHEET
