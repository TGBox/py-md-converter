"""Asynchronous conversion worker running inside a separate QThread."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from mdconv.engine import ConversionError, Options, convert
from mdconv.tools import ToolMissingError


class ConversionWorker(QObject):
    """Worker object to perform file conversions on a secondary thread."""

    started = Signal()
    file_started = Signal(str, int, int)
    file_finished = Signal(
        str, bool, str, list
    )  # (path, success, message, output_files)
    progress_updated = Signal(int, int)  # (current, total)
    log_message = Signal(
        str, str
    )  # (message, level: "info" | "success" | "warning" | "error")
    finished = Signal(int, int, int)  # (succeeded, failed, total)
    cancelled = Signal(int, int)  # (done, remaining)

    def __init__(
        self,
        files: list[Path],
        target_fmt: str,
        out_dir: Path | None,
        options: Options,
    ) -> None:
        super().__init__()
        self.files = files
        self.target_fmt = target_fmt
        self.out_dir = out_dir
        self.options = options
        self._is_cancelled = False

    def cancel(self) -> None:
        """Requests graceful cancellation of the current conversion batch."""
        self._is_cancelled = True

    def run(self) -> None:
        """Executes the conversion batch sequentially, reporting progress via signals."""
        self.started.emit()
        total = len(self.files)
        succeeded = 0
        failed = 0

        self.log_message.emit(
            f"Starte Konvertierung von {total} Datei(en) nach '{self.target_fmt.upper()}'...",
            "info",
        )

        for index, file_path in enumerate(self.files):
            if self._is_cancelled:
                remaining = total - (succeeded + failed)
                self.log_message.emit(
                    f"Konvertierung durch Benutzer abgebrochen. ({remaining} Datei(en) übersprungen)",
                    "warning",
                )
                self.cancelled.emit(succeeded + failed, remaining)
                return

            self.file_started.emit(str(file_path), index, total)
            self.progress_updated.emit(index, total)

            try:
                created = convert(
                    src=file_path,
                    dst_fmt=self.target_fmt,
                    out_dir=self.out_dir,
                    options=self.options,
                )
                succeeded += 1
                created_names = ", ".join(f.name for f in created)
                msg = f"Erfolgreich: {file_path.name} → {created_names}"
                self.log_message.emit(msg, "success")
                self.file_finished.emit(
                    str(file_path), True, msg, [str(f) for f in created]
                )
            except (ConversionError, ToolMissingError) as exc:
                failed += 1
                err_msg = f"Fehler bei {file_path.name}: {exc}"
                self.log_message.emit(err_msg, "error")
                self.file_finished.emit(str(file_path), False, str(exc), [])
            except Exception as exc:  # noqa: BLE001
                failed += 1
                err_msg = f"Unerwarteter Fehler bei {file_path.name}: {exc}"
                self.log_message.emit(err_msg, "error")
                self.file_finished.emit(str(file_path), False, str(exc), [])

            self.progress_updated.emit(index + 1, total)

        summary_level = (
            "success" if failed == 0 else ("warning" if succeeded > 0 else "error")
        )
        self.log_message.emit(
            f"Abgeschlossen: {succeeded} erfolgreich, {failed} fehlgeschlagen (Gesamt: {total}).",
            summary_level,
        )
        self.finished.emit(succeeded, failed, total)
