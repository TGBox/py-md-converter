"""Unit and integration tests for the PySide6 GUI components."""

from __future__ import annotations

import os

import pytest

# Ensure headless offscreen platform for Qt tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from mdconv.engine import Options
from mdconv.ui.dialogs import AboutDialog, FormatsDialog
from mdconv.ui.main_window import MainWindow
from mdconv.ui.theme import get_stylesheet
from mdconv.ui.widgets import FileTableWidget, LogWidget, format_file_size
from mdconv.ui.worker import ConversionWorker


@pytest.fixture(scope="session")
def qapp():
    """Initializes a shared QApplication instance for the test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_theme_stylesheets():
    dark_css = get_stylesheet("dark")
    light_css = get_stylesheet("light")
    assert "#1a1b26" in dark_css
    assert "#f8fafc" in light_css


def test_format_file_size():
    assert format_file_size(500) == "500 B"
    assert format_file_size(2048) == "2.0 KB"
    assert format_file_size(2 * 1024 * 1024) == "2.0 MB"


def test_file_table_widget(qapp, tmp_path):
    table = FileTableWidget()
    f1 = tmp_path / "test1.md"
    f1.write_text("# Hello", encoding="utf-8")
    d1 = tmp_path / "subfolder"
    d1.mkdir()

    # Adding paths
    assert table.add_path(f1) is True
    assert table.add_path(f1) is False  # Duplicate check
    assert table.add_path(d1) is True
    assert table.rowCount() == 2

    paths = table.get_paths()
    assert f1.resolve() in paths
    assert d1.resolve() in paths

    # Status update
    table.set_path_status(f1, "Erfolgreich ✓", "#10b981")
    assert table.item(0, 4).text() == "Erfolgreich ✓"

    # Reset
    table.reset_statuses()
    assert table.item(0, 4).text() == "Bereit"

    # Clear
    table.clear_all()
    assert table.rowCount() == 0
    assert len(table.get_paths()) == 0


def test_log_widget(qapp):
    log = LogWidget()
    log.append_message("Test Information", "info")
    log.append_message("Erfolg aufgetreten", "success")
    log.append_message("Achtung Warnung", "warning")
    log.append_message("Fehler aufgetreten", "error")

    plain = log.text_edit.toPlainText()
    assert "[INFO] Test Information" in plain
    assert "[ERFOLG] Erfolg aufgetreten" in plain
    assert "[WARNUNG] Achtung Warnung" in plain
    assert "[FEHLER] Fehler aufgetreten" in plain

    log.clear()
    assert log.text_edit.toPlainText() == ""


def test_dialogs(qapp):
    about = AboutDialog()
    assert "py-md-converter" in about.windowTitle()

    formats = FormatsDialog()
    assert "Unterstützte Formate" in formats.windowTitle()
    assert formats.findChild(FormatsDialog) is None  # simple smoke check


def test_worker_cancellation(qapp, tmp_path):
    f1 = tmp_path / "doc.md"
    f1.write_text("# Test", encoding="utf-8")
    worker = ConversionWorker(
        files=[f1],
        target_fmt="docx",
        out_dir=tmp_path / "out",
        options=Options(),
    )

    cancelled_called = []
    worker.cancelled.connect(lambda d, r: cancelled_called.append((d, r)))

    # Request cancellation before run
    worker.cancel()
    worker.run()

    assert len(cancelled_called) == 1
    assert cancelled_called[0] == (0, 1)


def test_main_window_lifecycle(qapp, tmp_path):
    win = MainWindow()
    assert "py-md-converter" in win.windowTitle()

    # Test file addition
    sample_file = tmp_path / "sample.md"
    sample_file.write_text("# Doc\n\nContent", encoding="utf-8")
    win._add_paths([sample_file])
    assert win.file_table.rowCount() == 1

    # Test format change and compatible count
    win.combo_target.setCurrentIndex(win.combo_target.findData("html"))
    assert "✓ 1 Datei(en) konvertierbar" in win.lbl_compatible_count.text()

    # Test theme toggling
    win.set_theme("light")
    assert win.current_theme == "light"
    win.set_theme("dark")
    assert win.current_theme == "dark"

    # Test fullscreen toggle
    assert not win.isFullScreen()
    win._toggle_fullscreen()
    assert win.isFullScreen()
    win._toggle_fullscreen()
    assert not win.isFullScreen()

    # Test close event (settings saved)
    win.close()


def test_file_table_reordering(qapp, tmp_path):
    table = FileTableWidget()
    f1 = tmp_path / "1.md"
    f2 = tmp_path / "2.md"
    f3 = tmp_path / "3.md"
    for f in (f1, f2, f3):
        f.write_text("# Test", encoding="utf-8")
        table.add_path(f)

    # Initial order: 1, 2, 3
    assert [p.name for p in table.get_paths()] == ["1.md", "2.md", "3.md"]

    # Select row 1 ("2.md") and move up
    table.selectRow(1)
    table.move_selected_up()
    assert [p.name for p in table.get_paths()] == ["2.md", "1.md", "3.md"]

    # Move down again
    table.selectRow(0)
    table.move_selected_down()
    assert [p.name for p in table.get_paths()] == ["1.md", "2.md", "3.md"]


def test_main_window_combine_mode(qapp, tmp_path):
    win = MainWindow()

    f1 = tmp_path / "intro.md"
    f1.write_text("# Intro", encoding="utf-8")
    f2 = tmp_path / "chapter.md"
    f2.write_text("# Chapter", encoding="utf-8")
    win._add_paths([f1, f2])

    # Select PDF target
    win.combo_target.setCurrentIndex(win.combo_target.findData("pdf"))
    assert not win.chk_combine_pdf.isHidden()

    # Toggle combine mode
    win.chk_combine_pdf.setChecked(True)
    assert not win.container_combine.isHidden()
    assert "werden kombiniert" in win.lbl_compatible_count.text()
    assert "kombiniertes PDF" in win.btn_convert.text()

    # Change combine title
    win.edit_combine_title.setText("Mein Handbuch")
    assert win.edit_combine_title.text() == "Mein Handbuch"

    win.close()


def test_worker_combine_mode(qapp, tmp_path):
    from mdconv.combine import CombineOptions

    f1 = tmp_path / "01.md"
    f1.write_text("# Erste Datei", encoding="utf-8")
    f2 = tmp_path / "02.md"
    f2.write_text("# Zweite Datei", encoding="utf-8")

    out_pdf = tmp_path / "output.pdf"
    worker = ConversionWorker(
        files=[f1, f2],
        target_fmt="pdf",
        out_dir=tmp_path,
        options=Options(),
        combine_mode=True,
        combine_options=CombineOptions(title="Test Kombi"),
        combine_out_file=out_pdf,
    )

    finished_called = []
    worker.finished.connect(lambda s, f, t: finished_called.append((s, f, t)))
    worker.run()

    assert len(finished_called) == 1
    assert finished_called[0] == (2, 0, 2)
    assert out_pdf.exists()
