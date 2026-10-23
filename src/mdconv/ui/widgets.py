"""Custom UI widgets for py-md-converter: FileTable and LogWidget."""

from __future__ import annotations

import datetime as dt
import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mdconv.engine import format_of


def format_file_size(size_bytes: int) -> str:
    """Formats file size in human readable units."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


class FileTableWidget(QTableWidget):
    """Table widget with native Drag & Drop support and context actions."""

    files_dropped = Signal(list)  # list[Path]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 5, parent)
        self.setHorizontalHeaderLabels(["Name", "Format", "Größe", "Pfad", "Status"])
        self.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Interactive
        )
        self.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )

        self.setColumnWidth(0, 220)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemDoubleClicked.connect(self._on_double_click)

        self._paths: list[Path] = []

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            paths = [
                Path(url.toLocalFile())
                for url in event.mimeData().urls()
                if url.toLocalFile()
            ]
            if paths:
                self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Delete):
            self.remove_selected()
        else:
            super().keyPressEvent(event)

    def add_path(self, path: Path) -> bool:
        """Adds a path if not already in the list. Returns True if added."""
        resolved = path.resolve()
        if resolved in self._paths:
            return False

        self._paths.append(resolved)
        row = self.rowCount()
        self.insertRow(row)

        name_item = QTableWidgetItem(resolved.name or str(resolved))
        name_item.setToolTip(str(resolved))

        if resolved.is_dir():
            fmt_str = "Ordner"
            try:
                child_count = sum(1 for f in resolved.rglob("*") if f.is_file())
                size_str = f"{child_count} Datei(en)"
                name_item.setToolTip(
                    f"{resolved}\n({child_count} Dateien in Unterordnern)"
                )
            except OSError:
                size_str = "-"
        else:
            fmt = format_of(resolved)
            fmt_str = fmt.upper() if fmt else (resolved.suffix or "-")
            try:
                size_str = format_file_size(resolved.stat().st_size)
            except OSError:
                size_str = "?"

        fmt_item = QTableWidgetItem(fmt_str)
        fmt_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        size_item = QTableWidgetItem(size_str)
        size_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        path_item = QTableWidgetItem(str(resolved.parent))
        path_item.setToolTip(str(resolved.parent))

        status_item = QTableWidgetItem("Bereit")
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        for item in (name_item, fmt_item, size_item, path_item, status_item):
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.setItem(row, 0, name_item)
        self.setItem(row, 1, fmt_item)
        self.setItem(row, 2, size_item)
        self.setItem(row, 3, path_item)
        self.setItem(row, 4, status_item)
        return True

    def get_paths(self) -> list[Path]:
        """Returns the list of unique paths currently in the table."""
        return list(self._paths)

    def remove_selected(self) -> None:
        """Removes the selected rows from the table and internal list."""
        selected_rows = sorted(
            {idx.row() for idx in self.selectedIndexes()}, reverse=True
        )
        for r in selected_rows:
            if 0 <= r < len(self._paths):
                del self._paths[r]
            self.removeRow(r)

    def clear_all(self) -> None:
        """Clears all entries from the table."""
        self._paths.clear()
        self.setRowCount(0)

    def set_path_status(
        self, path: Path, status_text: str, color_hex: str | None = None
    ) -> None:
        """Updates the status column for a given file path."""
        resolved = path.resolve()
        for r, p in enumerate(self._paths):
            if p == resolved:
                item = self.item(r, 4)
                if item:
                    item.setText(status_text)
                    if color_hex:
                        item.setForeground(QColor(color_hex))
                break

    def reset_statuses(self) -> None:
        """Resets all status columns back to 'Bereit'."""
        for r in range(self.rowCount()):
            item = self.item(r, 4)
            if item:
                item.setText("Bereit")
                item.setForeground(QColor("#7aa2f7"))

    def _swap_rows(self, r1: int, r2: int) -> None:
        """Swaps two rows in the internal paths list and the visual table."""
        self._paths[r1], self._paths[r2] = self._paths[r2], self._paths[r1]
        for col in range(self.columnCount()):
            item1 = self.takeItem(r1, col)
            item2 = self.takeItem(r2, col)
            if item2:
                self.setItem(r1, col, item2)
            if item1:
                self.setItem(r2, col, item1)

    def move_selected_up(self) -> None:
        """Moves selected rows one position upward."""
        selected_rows = sorted({idx.row() for idx in self.selectedIndexes()})
        if not selected_rows or selected_rows[0] == 0:
            return
        self.clearSelection()
        new_selection = []
        for r in selected_rows:
            self._swap_rows(r, r - 1)
            new_selection.append(r - 1)
        for r in new_selection:
            self.selectRow(r)

    def move_selected_down(self) -> None:
        """Moves selected rows one position downward."""
        selected_rows = sorted(
            {idx.row() for idx in self.selectedIndexes()}, reverse=True
        )
        if not selected_rows or selected_rows[0] >= self.rowCount() - 1:
            return
        self.clearSelection()
        new_selection = []
        for r in selected_rows:
            self._swap_rows(r, r + 1)
            new_selection.append(r + 1)
        for r in new_selection:
            self.selectRow(r)

    def _show_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        sel = self.selectedIndexes()
        has_selection = bool(sel)

        act_up = QAction("▲ Nach oben verschieben", self)
        act_up.setEnabled(has_selection)
        act_up.triggered.connect(self.move_selected_up)
        menu.addAction(act_up)

        act_down = QAction("▼ Nach unten verschieben", self)
        act_down.setEnabled(has_selection)
        act_down.triggered.connect(self.move_selected_down)
        menu.addAction(act_down)

        menu.addSeparator()

        act_remove = QAction("Auswahl entfernen", self)
        act_remove.setEnabled(has_selection)
        act_remove.triggered.connect(self.remove_selected)
        menu.addAction(act_remove)

        act_clear = QAction("Liste leeren", self)
        act_clear.setEnabled(self.rowCount() > 0)
        act_clear.triggered.connect(self.clear_all)
        menu.addAction(act_clear)

        menu.addSeparator()

        act_open_dir = QAction("Im Explorer anzeigen", self)
        act_open_dir.setEnabled(has_selection)
        act_open_dir.triggered.connect(self._open_selected_dir)
        menu.addAction(act_open_dir)

        menu.exec(self.mapToGlobal(pos))

    def _on_double_click(self, item: QTableWidgetItem) -> None:
        row = item.row()
        if 0 <= row < len(self._paths):
            self._open_path(self._paths[row])

    def _open_selected_dir(self) -> None:
        rows = {idx.row() for idx in self.selectedIndexes()}
        if rows:
            r = min(rows)
            if 0 <= r < len(self._paths):
                target = self._paths[r]
                folder = target if target.is_dir() else target.parent
                self._open_path(folder)

    @staticmethod
    def _open_path(path: Path) -> None:
        if os.name == "nt":
            os.startfile(str(path))
        else:
            subprocess.run(["xdg-open", str(path)], check=False)


class LogWidget(QWidget):
    """Structured rich-text log viewer with level tags and copy/clear controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 0, 4, 0)

        title = QLabel("Protokoll & Ausgaben")
        title.setStyleSheet("font-weight: 600; color: #7aa2f7;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.btn_copy = QPushButton("Kopieren")
        self.btn_copy.setToolTip("Gesamtes Protokoll in die Zwischenablage kopieren")
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        header_layout.addWidget(self.btn_copy)

        self.btn_clear = QPushButton("Leeren")
        self.btn_clear.setToolTip("Protokoll leeren")
        self.btn_clear.clicked.connect(self.clear)
        header_layout.addWidget(self.btn_clear)

        layout.addLayout(header_layout)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.text_edit)

    def append_message(self, message: str, level: str = "info") -> None:
        """Appends a timestamped log message with color coding."""
        now = dt.datetime.now().strftime("%H:%M:%S")

        colors = {
            "info": "#7aa2f7",
            "success": "#10b981",
            "warning": "#f59e0b",
            "error": "#ef4444",
        }
        labels = {
            "info": "INFO",
            "success": "ERFOLG",
            "warning": "WARNUNG",
            "error": "FEHLER",
        }

        color = colors.get(level, "#7aa2f7")
        tag = labels.get(level, "INFO")

        escaped = (
            message.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

        html = (
            f"<div style='margin-bottom: 3px; font-family: Consolas, monospace;'>"
            f"<span style='color: #64748b;'>[{now}]</span> "
            f"<b style='color: {color};'>[{tag}]</b> "
            f"<span>{escaped}</span>"
            f"</div>"
        )
        self.text_edit.append(html)
        self.text_edit.ensureCursorVisible()

    def clear(self) -> None:
        """Clears all text from the log widget."""
        self.text_edit.clear()

    def copy_to_clipboard(self) -> None:
        """Copies plain text of the log to system clipboard."""
        text = self.text_edit.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.append_message("Protokoll in Zwischenablage kopiert.", "info")
