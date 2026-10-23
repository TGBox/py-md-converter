"""Main application window for py-md-converter using PySide6."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread
from PySide6.QtGui import (
    QAction,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from mdconv import __version__
from mdconv.combine import CombineOptions, find_markdown_files, natural_sort_key
from mdconv.engine import Options, collect_inputs, format_of
from mdconv.ui.dialogs import (
    AboutDialog,
    FormatsDialog,
    is_pandoc_available,
    is_typst_available,
)
from mdconv.ui.theme import ThemeMode, get_stylesheet
from mdconv.ui.widgets import FileTableWidget, LogWidget
from mdconv.ui.worker import ConversionWorker

ORGANIZATION_NAME = "Data-AL"
APPLICATION_NAME = "py-md-converter"

FORMATS = ["docx", "pdf", "html", "md", "xlsx", "csv"]
DELIMITER_OPTIONS = {
    "Komma (,)": ",",
    "Semikolon (;)": ";",
    "Tabulator (\\t)": "\t",
}


class MainWindow(QMainWindow):
    """The central application window for py-md-converter."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"py-md-converter v{__version__}")
        self.setMinimumSize(850, 680)
        self.setAcceptDrops(True)

        self.settings = QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
        self.current_theme: ThemeMode = "dark"

        self.worker_thread: QThread | None = None
        self.current_worker: ConversionWorker | None = None

        self._setup_ui()
        self._setup_menus()
        self._load_settings()
        self._update_compatible_count()
        self._update_tool_status_bar()

    # ---------- UI Setup ----------

    def _setup_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(10)

        # Splitter to allow dynamic resizing of file list vs log
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        # Upper container: Files & Options
        upper_container = QWidget()
        upper_layout = QVBoxLayout(upper_container)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setSpacing(8)

        # 1. File List Section
        file_group = QGroupBox("Eingabedateien & Ordner")
        file_layout = QVBoxLayout(file_group)
        file_layout.setSpacing(6)

        # Table
        self.file_table = FileTableWidget()
        self.file_table.files_dropped.connect(self._add_paths)
        file_layout.addWidget(self.file_table)

        # File actions bar
        file_actions_layout = QHBoxLayout()
        file_actions_layout.setSpacing(6)

        self.btn_add_files = QPushButton("Dateien hinzufügen…")
        self.btn_add_files.setToolTip("Dateien zur Konvertierung auswählen (Strg+O)")
        self.btn_add_files.clicked.connect(self._on_add_files)
        file_actions_layout.addWidget(self.btn_add_files)

        self.btn_add_folder = QPushButton("Ordner hinzufügen…")
        self.btn_add_folder.setToolTip(
            "Ganzen Ordner zur Konvertierung auswählen (Strg+Umschalt+O)"
        )
        self.btn_add_folder.clicked.connect(self._on_add_folder)
        file_actions_layout.addWidget(self.btn_add_folder)

        self.btn_remove = QPushButton("Auswahl entfernen")
        self.btn_remove.setToolTip("Ausgewählte Dateien aus der Liste entfernen (Entf)")
        self.btn_remove.clicked.connect(self.file_table.remove_selected)
        file_actions_layout.addWidget(self.btn_remove)

        self.btn_move_up = QPushButton("▲ Nach oben")
        self.btn_move_up.setToolTip("Ausgewählte Einträge nach oben verschieben")
        self.btn_move_up.clicked.connect(self.file_table.move_selected_up)
        file_actions_layout.addWidget(self.btn_move_up)

        self.btn_move_down = QPushButton("▼ Nach unten")
        self.btn_move_down.setToolTip("Ausgewählte Einträge nach unten verschieben")
        self.btn_move_down.clicked.connect(self.file_table.move_selected_down)
        file_actions_layout.addWidget(self.btn_move_down)

        self.btn_clear = QPushButton("Alle leeren")
        self.btn_clear.setToolTip("Gesamte Dateiliste zurücksetzen")
        self.btn_clear.clicked.connect(self._on_clear_files)
        file_actions_layout.addWidget(self.btn_clear)

        file_actions_layout.addStretch()

        self.lbl_file_count = QLabel("0 Dateien geladen")
        self.lbl_file_count.setObjectName("mutedLabel")
        file_actions_layout.addWidget(self.lbl_file_count)

        file_layout.addLayout(file_actions_layout)
        upper_layout.addWidget(file_group)

        # 2. Options Section
        options_group = QGroupBox("Konvertierungs-Optionen")
        options_layout = QVBoxLayout(options_group)
        options_layout.setSpacing(8)

        # Row 1: Target Format & Combine Checkbox
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Zielformat:"))
        self.combo_target = QComboBox()
        for fmt in FORMATS:
            self.combo_target.addItem(fmt.upper(), fmt)
        self.combo_target.currentIndexChanged.connect(self._on_target_format_changed)
        row1.addWidget(self.combo_target)

        self.chk_combine_pdf = QCheckBox(
            "Markdown-Dateien zu einem PDF kombinieren (mit Inhaltsverzeichnis)"
        )
        self.chk_combine_pdf.setStyleSheet(
            "font-weight: 600; color: #7aa2f7; margin-left: 15px;"
        )
        self.chk_combine_pdf.setToolTip(
            "Führt alle Markdown-Dateien in ein einziges strukturiertes PDF-Dokument "
            "mit klickbarem Inhaltsverzeichnis am Anfang zusammen."
        )
        self.chk_combine_pdf.toggled.connect(self._on_combine_toggled)
        row1.addWidget(self.chk_combine_pdf)

        self.lbl_compatible_count = QLabel("")
        self.lbl_compatible_count.setStyleSheet(
            "color: #10b981; font-weight: 600; margin-left: 10px;"
        )
        row1.addWidget(self.lbl_compatible_count)
        row1.addStretch()
        options_layout.addLayout(row1)

        # Row 1b: PDF Combine Detail Options (Title, TOC-Depth, Numbering, Pagebreak)
        self.container_combine = QWidget()
        combine_layout = QHBoxLayout(self.container_combine)
        combine_layout.setContentsMargins(0, 2, 0, 2)
        combine_layout.setSpacing(10)

        combine_layout.addWidget(QLabel("Dokumenttitel:"))
        self.edit_combine_title = QLineEdit("Dokumentation")
        self.edit_combine_title.setPlaceholderText(
            "Titel für Deckblatt & Inhaltsverzeichnis"
        )
        self.edit_combine_title.setMaximumWidth(220)
        combine_layout.addWidget(self.edit_combine_title)

        combine_layout.addWidget(QLabel("TOC-Tiefe:"))
        self.spin_toc_depth = QSpinBox()
        self.spin_toc_depth.setRange(1, 5)
        self.spin_toc_depth.setValue(3)
        self.spin_toc_depth.setToolTip(
            "Gliederungstiefe des Inhaltsverzeichnisses (Ebenen 1 bis 5)"
        )
        combine_layout.addWidget(self.spin_toc_depth)

        self.chk_combine_numbering = QCheckBox("Kapitel nummerieren (1, 1.1)")
        self.chk_combine_numbering.setChecked(True)
        combine_layout.addWidget(self.chk_combine_numbering)

        self.chk_combine_pagebreak = QCheckBox("Seitenumbruch je Datei")
        self.chk_combine_pagebreak.setChecked(True)
        combine_layout.addWidget(self.chk_combine_pagebreak)

        combine_layout.addStretch()
        self.container_combine.setVisible(False)
        options_layout.addWidget(self.container_combine)

        # Row 2: Output Directory
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Ausgabeordner:"))
        self.edit_out_dir = QLineEdit()
        self.edit_out_dir.setPlaceholderText("Standard: neben den Quelldateien")
        row2.addWidget(self.edit_out_dir)

        btn_browse_out = QPushButton("Durchsuchen…")
        btn_browse_out.clicked.connect(self._on_browse_out_dir)
        row2.addWidget(btn_browse_out)

        self.btn_open_out_dir = QPushButton("Ordner öffnen")
        self.btn_open_out_dir.setToolTip("Ausgabeordner im Windows Explorer öffnen")
        self.btn_open_out_dir.clicked.connect(self._on_open_out_dir)
        row2.addWidget(self.btn_open_out_dir)
        options_layout.addLayout(row2)

        # Row 3: Word Reference Doc (for MD -> DOCX)
        self.row_reference = QHBoxLayout()
        self.lbl_reference = QLabel("Word-Vorlage:")
        self.row_reference.addWidget(self.lbl_reference)
        self.edit_reference = QLineEdit()
        self.edit_reference.setPlaceholderText(
            "Optional: .docx-Formatvorlage für MD → DOCX"
        )
        self.row_reference.addWidget(self.edit_reference)

        self.btn_browse_ref = QPushButton("Durchsuchen…")
        self.btn_browse_ref.clicked.connect(self._on_browse_reference)
        self.row_reference.addWidget(self.btn_browse_ref)
        options_layout.addLayout(self.row_reference)

        # Row 4: CSV Delimiter & Checkboxes
        row4 = QHBoxLayout()
        self.lbl_delimiter = QLabel("CSV-Trennzeichen:")
        row4.addWidget(self.lbl_delimiter)
        self.combo_delimiter = QComboBox()
        for label, val in DELIMITER_OPTIONS.items():
            self.combo_delimiter.addItem(label, val)
        row4.addWidget(self.combo_delimiter)

        row4.addSpacing(20)
        self.chk_recursive = QCheckBox("Unterordner rekursiv durchsuchen")
        self.chk_recursive.setChecked(True)
        self.chk_recursive.toggled.connect(self._on_recursive_toggled)
        row4.addWidget(self.chk_recursive)

        self.chk_overwrite = QCheckBox("Vorhandene Dateien überschreiben")
        self.chk_overwrite.toggled.connect(self._update_compatible_count)
        row4.addWidget(self.chk_overwrite)

        row4.addStretch()
        options_layout.addLayout(row4)

        upper_layout.addWidget(options_group)
        splitter.addWidget(upper_container)

        # Lower container: Controls, Progress & Log
        lower_container = QWidget()
        lower_layout = QVBoxLayout(lower_container)
        lower_layout.setContentsMargins(0, 4, 0, 0)
        lower_layout.setSpacing(8)

        # Progress and Action Buttons
        controls_layout = QHBoxLayout()
        self.btn_convert = QPushButton("▶  Jetzt Konvertieren")
        self.btn_convert.setObjectName("primaryButton")
        self.btn_convert.setToolTip("Stapelkonvertierung starten (Strg+Eingabe)")
        self.btn_convert.clicked.connect(self._on_start_conversion)
        controls_layout.addWidget(self.btn_convert)

        self.btn_cancel = QPushButton("■  Abbrechen")
        self.btn_cancel.setObjectName("dangerButton")
        self.btn_cancel.setToolTip("Laufende Konvertierung abbrechen (Esc)")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel_conversion)
        controls_layout.addWidget(self.btn_cancel)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v / %m Dateien (%p%)")
        controls_layout.addWidget(self.progress_bar)

        lower_layout.addLayout(controls_layout)

        # Log widget
        self.log_widget = LogWidget()
        lower_layout.addWidget(self.log_widget)

        splitter.addWidget(lower_container)
        splitter.setSizes([420, 240])

        main_layout.addWidget(splitter)

    # ---------- Menu Setup ----------

    def _setup_menus(self) -> None:
        menubar = self.menuBar()

        # 1. Datei
        menu_file = menubar.addMenu("&Datei")

        act_add_files = QAction("&Dateien hinzufügen…", self)
        act_add_files.setShortcut(QKeySequence.StandardKey.Open)
        act_add_files.triggered.connect(self._on_add_files)
        menu_file.addAction(act_add_files)

        act_add_folder = QAction("&Ordner hinzufügen…", self)
        act_add_folder.setShortcut("Ctrl+Shift+O")
        act_add_folder.triggered.connect(self._on_add_folder)
        menu_file.addAction(act_add_folder)

        menu_file.addSeparator()

        act_open_out = QAction("Ausgabeordner im Explorer &öffnen", self)
        act_open_out.setShortcut("Ctrl+E")
        act_open_out.triggered.connect(self._on_open_out_dir)
        menu_file.addAction(act_open_out)

        menu_file.addSeparator()

        act_exit = QAction("&Beenden", self)
        act_exit.setShortcut(QKeySequence.StandardKey.Quit)
        act_exit.triggered.connect(self.close)
        menu_file.addAction(act_exit)

        # 2. Bearbeiten
        menu_edit = menubar.addMenu("&Bearbeiten")

        act_remove = QAction("Auswahl &entfernen", self)
        act_remove.setShortcut(QKeySequence.StandardKey.Delete)
        act_remove.triggered.connect(self.file_table.remove_selected)
        menu_edit.addAction(act_remove)

        act_clear_files = QAction("Dateiliste &leeren", self)
        act_clear_files.triggered.connect(self._on_clear_files)
        menu_edit.addAction(act_clear_files)

        menu_edit.addSeparator()

        act_clear_log = QAction("&Protokoll leeren", self)
        act_clear_log.triggered.connect(self.log_widget.clear)
        menu_edit.addAction(act_clear_log)

        # 3. Ansicht
        menu_view = menubar.addMenu("&Ansicht")

        self.act_fullscreen = QAction("&Vollbildmodus", self)
        self.act_fullscreen.setShortcut("F11")
        self.act_fullscreen.setCheckable(True)
        self.act_fullscreen.triggered.connect(self._toggle_fullscreen)
        menu_view.addAction(self.act_fullscreen)

        menu_view.addSeparator()

        act_theme_dark = QAction("&Dunkles Design (Dark Theme)", self)
        act_theme_dark.triggered.connect(lambda: self.set_theme("dark"))
        menu_view.addAction(act_theme_dark)

        act_theme_light = QAction("&Helles Design (Light Theme)", self)
        act_theme_light.triggered.connect(lambda: self.set_theme("light"))
        menu_view.addAction(act_theme_light)

        # 4. Werkzeuge
        menu_tools = menubar.addMenu("&Werkzeuge")

        act_formats = QAction("&Unterstützte Formate && Tools…", self)
        act_formats.setShortcut("F1")
        act_formats.triggered.connect(self._show_formats_dialog)
        menu_tools.addAction(act_formats)

        # 5. Hilfe
        menu_help = menubar.addMenu("&Hilfe")

        act_about = QAction("&Über py-md-converter…", self)
        act_about.triggered.connect(self._show_about_dialog)
        menu_help.addAction(act_about)

    # ---------- Drag & Drop ----------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            paths = [
                Path(url.toLocalFile())
                for url in event.mimeData().urls()
                if url.toLocalFile()
            ]
            if paths:
                self._add_paths(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    # ---------- File Operations ----------

    def _on_add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Dateien zur Konvertierung wählen",
            "",
            "Alle unterstützten Formate (*.md *.markdown *.docx *.html *.htm *.pdf *.xlsx *.csv);;Alle Dateien (*.*)",
        )
        if files:
            self._add_paths([Path(f) for f in files])

    def _on_add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Ordner zur Konvertierung wählen"
        )
        if folder:
            self._add_paths([Path(folder)])

    def _on_recursive_toggled(self, checked: bool) -> None:
        self._update_compatible_count()

    def _add_paths(self, paths: list[Path]) -> None:
        added_count = 0
        for raw in paths:
            p = Path(raw).resolve()
            if p.is_dir():
                # Always recursively discover all supported files in the folder and its subdirectories
                folder_files = [
                    f.resolve()
                    for f in p.rglob("*")
                    if f.is_file() and format_of(f) is not None
                ]
                folder_files.sort(key=natural_sort_key)
                if folder_files:
                    for f in folder_files:
                        if self.file_table.add_path(f):
                            added_count += 1
                    self.log_widget.append_message(
                        f"Ordner '{p.name}' durchsucht: {len(folder_files)} Datei(en) in Unterverzeichnissen geladen.",
                        "info",
                    )
                else:
                    if self.file_table.add_path(p):
                        added_count += 1
                    self.log_widget.append_message(
                        f"Ordner '{p.name}' hinzugefügt (keine passenden Dateien gefunden).",
                        "warning",
                    )
            else:
                if self.file_table.add_path(p):
                    added_count += 1

        total = self.file_table.rowCount()
        self.lbl_file_count.setText(f"{total} Datei(en) geladen")
        self._update_compatible_count()
        if added_count > 0:
            self.log_widget.append_message(
                f"{added_count} Eintrag/Einträge hinzugefügt.", "info"
            )

    def _on_clear_files(self) -> None:
        self.file_table.clear_all()
        self.lbl_file_count.setText("0 Dateien geladen")
        self._update_compatible_count()

    def _on_browse_out_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Ausgabeordner auswählen")
        if folder:
            self.edit_out_dir.setText(folder)

    def _on_open_out_dir(self) -> None:
        out_text = self.edit_out_dir.text().strip()
        path = Path(out_text) if out_text else None
        if not path or not path.exists():
            # If not explicitly set, try first file's parent or current working dir
            paths = self.file_table.get_paths()
            path = paths[0].parent if paths else Path.cwd()

        if os.name == "nt":
            os.startfile(str(path))
        else:
            subprocess.run(["xdg-open", str(path)], check=False)

    def _on_browse_reference(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Word-Vorlage auswählen", "", "Word-Dokumente (*.docx)"
        )
        if file_path:
            self.edit_reference.setText(file_path)

    def _on_combine_toggled(self, checked: bool) -> None:
        self.container_combine.setVisible(checked)
        self.btn_convert.setText(
            "▶  Als kombiniertes PDF erstellen" if checked else "▶  Jetzt Konvertieren"
        )
        self._update_compatible_count()

    def _on_target_format_changed(self) -> None:
        target_fmt = self.combo_target.currentData()
        is_docx = target_fmt == "docx"
        self.lbl_reference.setEnabled(is_docx)
        self.edit_reference.setEnabled(is_docx)
        self.btn_browse_ref.setEnabled(is_docx)

        is_csv = target_fmt == "csv"
        self.lbl_delimiter.setEnabled(is_csv)
        self.combo_delimiter.setEnabled(is_csv)

        is_pdf = target_fmt == "pdf"
        self.chk_combine_pdf.setVisible(is_pdf)
        self.container_combine.setVisible(is_pdf and self.chk_combine_pdf.isChecked())
        if not is_pdf:
            self.btn_convert.setText("▶  Jetzt Konvertieren")
        elif self.chk_combine_pdf.isChecked():
            self.btn_convert.setText("▶  Als kombiniertes PDF erstellen")

        self._update_compatible_count()

    def _update_compatible_count(self) -> None:
        target_fmt = self.combo_target.currentData() or "docx"
        paths = self.file_table.get_paths()
        if not paths:
            self.lbl_compatible_count.setText("")
            return

        if target_fmt == "pdf" and self.chk_combine_pdf.isChecked():
            # In combine mode, always search recursively through folder structures
            md_files = find_markdown_files(paths, recursive=True)
            count = len(md_files)
            if count == 0:
                self.lbl_compatible_count.setText(
                    "⚠ Keine Markdown-Dateien zum Kombinieren"
                )
                self.lbl_compatible_count.setStyleSheet(
                    "color: #ef4444; font-weight: 600; margin-left: 10px;"
                )
            else:
                self.lbl_compatible_count.setText(
                    f"✓ {count} Markdown-Datei(en) werden kombiniert"
                )
                self.lbl_compatible_count.setStyleSheet(
                    "color: #10b981; font-weight: 600; margin-left: 10px;"
                )
            return

        resolved_files = collect_inputs(
            paths, target_fmt, self.chk_recursive.isChecked()
        )
        count = len(resolved_files)
        if count == 0:
            self.lbl_compatible_count.setText(
                "⚠ Keine konvertierbaren Dateien für dieses Format"
            )
            self.lbl_compatible_count.setStyleSheet(
                "color: #ef4444; font-weight: 600; margin-left: 10px;"
            )
        else:
            self.lbl_compatible_count.setText(f"✓ {count} Datei(en) konvertierbar")
            self.lbl_compatible_count.setStyleSheet(
                "color: #10b981; font-weight: 600; margin-left: 10px;"
            )

    # ---------- Execution & Threading ----------

    def _on_start_conversion(self) -> None:
        paths = self.file_table.get_paths()
        if not paths:
            QMessageBox.information(
                self,
                "Keine Dateien",
                "Bitte fügen Sie zuerst Dateien oder Ordner zur Liste hinzu.",
            )
            return

        target_fmt = self.combo_target.currentData()
        recursive = self.chk_recursive.isChecked()
        is_combine = target_fmt == "pdf" and self.chk_combine_pdf.isChecked()

        out_dir_text = self.edit_out_dir.text().strip()
        out_dir = Path(out_dir_text) if out_dir_text else None
        overwrite = self.chk_overwrite.isChecked()

        if is_combine:
            resolved_files: list[Path] = []
            for p in paths:
                if p.is_file() and p.suffix.lower() in {".md", ".markdown"}:
                    if p not in resolved_files:
                        resolved_files.append(p)
                elif p.is_dir():
                    for f in find_markdown_files([p], recursive=True):
                        if f not in resolved_files:
                            resolved_files.append(f)

            if not resolved_files:
                msg = "Keine Markdown-Dateien zum Kombinieren gefunden."
                self.log_widget.append_message(msg, "warning")
                QMessageBox.warning(self, "Keine Markdown-Dateien", msg)
                return

            doc_title = self.edit_combine_title.text().strip() or "Dokumentation"
            if out_dir_text:
                candidate = Path(out_dir_text)
                if candidate.suffix.lower() == ".pdf":
                    target_pdf = candidate
                else:
                    target_pdf = candidate / f"{doc_title}.pdf"
            else:
                target_pdf = resolved_files[0].parent / f"{doc_title}.pdf"

            combine_options = CombineOptions(
                title=doc_title,
                toc=True,
                toc_depth=self.spin_toc_depth.value(),
                pagebreaks=self.chk_combine_pagebreak.isChecked(),
                number_sections=self.chk_combine_numbering.isChecked(),
                overwrite=overwrite,
            )
            worker_files = resolved_files
            options = Options(overwrite=overwrite)
        else:
            resolved_files = collect_inputs(paths, target_fmt, recursive)
            if not resolved_files:
                msg = f"Keine konvertierbaren Dateien für das Zielformat '{target_fmt.upper()}' gefunden."
                self.log_widget.append_message(msg, "warning")
                QMessageBox.warning(self, "Keine kompatiblen Dateien", msg)
                return

            ref_doc_text = self.edit_reference.text().strip()
            ref_doc = Path(ref_doc_text) if ref_doc_text else None
            delimiter = self.combo_delimiter.currentData() or ","

            options = Options(
                reference_doc=ref_doc,
                csv_delimiter=delimiter,
                overwrite=overwrite,
            )
            combine_options = None
            target_pdf = None
            worker_files = resolved_files

        self.file_table.reset_statuses()
        self.progress_bar.setRange(0, len(worker_files))
        self.progress_bar.setValue(0)

        # UI State during processing
        self.btn_convert.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_add_files.setEnabled(False)
        self.btn_add_folder.setEnabled(False)
        self.btn_remove.setEnabled(False)
        self.btn_clear.setEnabled(False)
        self.btn_move_up.setEnabled(False)
        self.btn_move_down.setEnabled(False)

        # Spawn QThread
        self.worker_thread = QThread(self)
        self.current_worker = ConversionWorker(
            files=worker_files,
            target_fmt=target_fmt,
            out_dir=out_dir,
            options=options,
            combine_mode=is_combine,
            combine_options=combine_options,
            combine_out_file=target_pdf,
        )
        self.current_worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.current_worker.run)
        self.current_worker.progress_updated.connect(self._on_worker_progress)
        self.current_worker.file_started.connect(self._on_file_started)
        self.current_worker.file_finished.connect(self._on_file_finished)
        self.current_worker.log_message.connect(self.log_widget.append_message)
        self.current_worker.finished.connect(self._on_conversion_finished)
        self.current_worker.cancelled.connect(self._on_conversion_cancelled)

        self.current_worker.finished.connect(self.worker_thread.quit)
        self.current_worker.cancelled.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._cleanup_worker)

        self.worker_thread.start()
        self.statusBar().showMessage(f"Konvertiere {len(resolved_files)} Dateien...")

    def _on_cancel_conversion(self) -> None:
        if self.current_worker:
            self.btn_cancel.setEnabled(False)
            self.btn_cancel.setText("Breche ab…")
            self.current_worker.cancel()

    def _on_worker_progress(self, current: int, total: int) -> None:
        self.progress_bar.setValue(current)

    def _on_file_started(self, path_str: str, index: int, total: int) -> None:
        p = Path(path_str)
        self.file_table.set_path_status(p, "Wird konvertiert…", "#7aa2f7")
        self.statusBar().showMessage(f"[{index + 1}/{total}] Konvertiere {p.name}...")

    def _on_file_finished(
        self, path_str: str, success: bool, message: str, outputs: list[str]
    ) -> None:
        p = Path(path_str)
        if success:
            self.file_table.set_path_status(p, "Erfolgreich ✓", "#10b981")
        else:
            self.file_table.set_path_status(p, "Fehler ✗", "#ef4444")

    def _on_conversion_finished(self, succeeded: int, failed: int, total: int) -> None:
        self.statusBar().showMessage(
            f"Fertig: {succeeded} erfolgreich, {failed} fehlgeschlagen von {total}."
        )

    def _on_conversion_cancelled(self, done: int, remaining: int) -> None:
        self.statusBar().showMessage(
            f"Abgebrochen ({done} verarbeitet, {remaining} übersprungen)."
        )

    def _cleanup_worker(self) -> None:
        self.btn_convert.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setText("■  Abbrechen")
        self.btn_add_files.setEnabled(True)
        self.btn_add_folder.setEnabled(True)
        self.btn_remove.setEnabled(True)
        self.btn_clear.setEnabled(True)
        self.btn_move_up.setEnabled(True)
        self.btn_move_down.setEnabled(True)

        self.current_worker = None
        self.worker_thread = None

    # ---------- Theme & Window State ----------

    def set_theme(self, theme: ThemeMode) -> None:
        """Applies stylesheet and stores theme preference."""
        self.current_theme = theme
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_stylesheet(theme))
        self.settings.setValue("theme", theme)
        self._update_tool_status_bar()

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.act_fullscreen.setChecked(False)
        else:
            self.showFullScreen()
            self.act_fullscreen.setChecked(True)

    def _show_about_dialog(self) -> None:
        dlg = AboutDialog(self)
        dlg.exec()

    def _show_formats_dialog(self) -> None:
        dlg = FormatsDialog(self)
        dlg.exec()

    def _update_tool_status_bar(self) -> None:
        pandoc_ok = is_pandoc_available()
        typst_ok = is_typst_available()
        status = (
            f"Pandoc: {'Bereit ✓' if pandoc_ok else 'Nicht gefunden ✗'}  |  "
            f"Typst: {'Gefunden ✓' if typst_ok else 'Fehlt (MD→PDF) ✗'}  |  "
            f"Design: {self.current_theme.capitalize()}"
        )
        self.statusBar().showMessage(status)

    def _load_settings(self) -> None:
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        saved_theme = self.settings.value("theme", "dark")
        self.set_theme(saved_theme if saved_theme in ("dark", "light") else "dark")

        saved_out_dir = self.settings.value("out_dir", "")
        if saved_out_dir:
            self.edit_out_dir.setText(str(saved_out_dir))

        saved_target = self.settings.value("target_format", "docx")
        idx = self.combo_target.findData(saved_target)
        if idx >= 0:
            self.combo_target.setCurrentIndex(idx)

        self.chk_recursive.setChecked(self.settings.value("recursive", True, type=bool))
        self.chk_overwrite.setChecked(
            self.settings.value("overwrite", False, type=bool)
        )
        self.chk_combine_pdf.setChecked(
            self.settings.value("combine_pdf", False, type=bool)
        )
        self.edit_combine_title.setText(
            self.settings.value("combine_title", "Dokumentation")
        )
        self.spin_toc_depth.setValue(self.settings.value("toc_depth", 3, type=int))
        self.chk_combine_numbering.setChecked(
            self.settings.value("combine_numbering", True, type=bool)
        )
        self.chk_combine_pagebreak.setChecked(
            self.settings.value("combine_pagebreak", True, type=bool)
        )

    def closeEvent(self, event) -> None:
        """Saves window geometry and settings before exiting."""
        if self.worker_thread and self.worker_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Konvertierung läuft",
                "Eine Konvertierung wird gerade ausgeführt. Wirklich beenden?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

            if self.current_worker:
                self.current_worker.cancel()
            self.worker_thread.quit()
            self.worker_thread.wait(2000)

        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("theme", self.current_theme)
        self.settings.setValue("out_dir", self.edit_out_dir.text())
        self.settings.setValue("target_format", self.combo_target.currentData())
        self.settings.setValue("recursive", self.chk_recursive.isChecked())
        self.settings.setValue("overwrite", self.chk_overwrite.isChecked())
        self.settings.setValue("combine_pdf", self.chk_combine_pdf.isChecked())
        self.settings.setValue("combine_title", self.edit_combine_title.text())
        self.settings.setValue("toc_depth", self.spin_toc_depth.value())
        self.settings.setValue(
            "combine_numbering", self.chk_combine_numbering.isChecked()
        )
        self.settings.setValue(
            "combine_pagebreak", self.chk_combine_pagebreak.isChecked()
        )
        super().closeEvent(event)


def main() -> None:
    """Direct entry point for launching MainWindow."""
    import sys

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("py-md-converter")
    app.setOrganizationName("Data-AL")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
