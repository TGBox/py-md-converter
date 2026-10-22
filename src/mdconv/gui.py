"""Tkinter-Oberfläche mit Drag & Drop (tkinterdnd2, falls vorhanden)."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from mdconv import __version__
from mdconv.engine import (
    ConversionError,
    Options,
    collect_inputs,
    convert,
    supported_conversions,
)
from mdconv.tools import ToolMissingError

HAS_DND = False
DND_FILES = None
TkinterDnD = None

try:
    import importlib

    _dnd = importlib.import_module("tkinterdnd2")
    DND_FILES = getattr(_dnd, "DND_FILES", None)
    TkinterDnD = getattr(_dnd, "TkinterDnD", None)
    HAS_DND = True
except ImportError:  # GUI funktioniert auch ohne, dann nur per Dateidialog
    HAS_DND = False

FORMATS = sorted({dst for _, dst in supported_conversions()})
DELIMITERS = {",": ",", ";": ";", "Tab": "\t"}


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.inputs: list[Path] = []
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None

        root.title(f"py-md-converter {__version__}")
        root.geometry("760x620")
        root.minsize(620, 520)

        self.target = tk.StringVar(value="docx")
        self.out_dir = tk.StringVar()
        self.reference = tk.StringVar()
        self.delimiter = tk.StringVar(value=",")
        self.recursive = tk.BooleanVar(value=False)
        self.overwrite = tk.BooleanVar(value=False)

        self._build()
        self.root.after(100, self._poll)

    # ---------- Aufbau ----------

    def _build(self) -> None:
        pad = {"padx": 10, "pady": 6}

        files = ttk.LabelFrame(self.root, text="Eingabe")
        files.pack(fill="both", expand=True, **pad)
        hint = (
            "Dateien oder Ordner hierher ziehen"
            if HAS_DND
            else "Dateien oder Ordner hinzufügen"
        )
        ttk.Label(files, text=hint, foreground="gray").pack(
            anchor="w", padx=8, pady=(4, 0)
        )

        self.listbox = tk.Listbox(files, selectmode="extended", height=8)
        self.listbox.pack(fill="both", expand=True, padx=8, pady=4)
        if HAS_DND:
            self.listbox.drop_target_register(DND_FILES)
            self.listbox.dnd_bind("<<Drop>>", self._on_drop)

        bar = ttk.Frame(files)
        bar.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Button(bar, text="Dateien…", command=self._add_files).pack(side="left")
        ttk.Button(bar, text="Ordner…", command=self._add_folder).pack(
            side="left", padx=4
        )
        ttk.Button(bar, text="Entfernen", command=self._remove_selected).pack(
            side="left"
        )
        ttk.Button(bar, text="Leeren", command=self._clear).pack(side="left", padx=4)

        opts = ttk.LabelFrame(self.root, text="Optionen")
        opts.pack(fill="x", **pad)
        opts.columnconfigure(1, weight=1)

        ttk.Label(opts, text="Zielformat").grid(
            row=0, column=0, sticky="w", padx=8, pady=4
        )
        ttk.Combobox(
            opts, textvariable=self.target, values=FORMATS, state="readonly", width=10
        ).grid(row=0, column=1, sticky="w", pady=4)

        self._path_row(
            opts,
            1,
            "Ausgabeordner",
            self.out_dir,
            self._pick_out_dir,
            "leer = neben der Quelldatei",
        )
        self._path_row(
            opts,
            2,
            "Word-Vorlage",
            self.reference,
            self._pick_reference,
            "optional, nur für MD → DOCX",
        )

        ttk.Label(opts, text="CSV-Trennzeichen").grid(
            row=3, column=0, sticky="w", padx=8, pady=4
        )
        ttk.Combobox(
            opts,
            textvariable=self.delimiter,
            values=list(DELIMITERS),
            state="readonly",
            width=6,
        ).grid(row=3, column=1, sticky="w", pady=4)

        checks = ttk.Frame(opts)
        checks.grid(row=4, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 6))
        ttk.Checkbutton(
            checks, text="Unterordner einbeziehen", variable=self.recursive
        ).pack(side="left")
        ttk.Checkbutton(
            checks, text="Vorhandene Dateien überschreiben", variable=self.overwrite
        ).pack(side="left", padx=12)

        run = ttk.Frame(self.root)
        run.pack(fill="x", **pad)
        self.button = ttk.Button(run, text="Konvertieren", command=self._start)
        self.button.pack(side="left")
        self.progress = ttk.Progressbar(run, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=10)

        logf = ttk.LabelFrame(self.root, text="Protokoll")
        logf.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(logf, height=8, state="disabled", wrap="word")
        scroll = ttk.Scrollbar(logf, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True, padx=(8, 0), pady=4)
        self.log.tag_configure("error", foreground="#b00020")
        self.log.tag_configure("ok", foreground="#1b5e20")

    def _path_row(self, parent, row, label, var, command, hint) -> None:
        ttk.Label(parent, text=label).grid(
            row=row, column=0, sticky="w", padx=8, pady=4
        )
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(parent, text="…", width=3, command=command).grid(
            row=row, column=2, padx=8
        )
        ttk.Label(parent, text=hint, foreground="gray").grid(
            row=row, column=3, sticky="w", padx=(0, 8)
        )

    # ---------- Eingabe ----------

    def _add(self, paths) -> None:
        for p in map(Path, paths):
            if p not in self.inputs:
                self.inputs.append(p)
                self.listbox.insert("end", str(p))

    def _on_drop(self, event) -> None:
        self._add(self.root.tk.splitlist(event.data))

    def _add_files(self) -> None:
        self._add(filedialog.askopenfilenames(title="Dateien wählen"))

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Ordner wählen")
        if folder:
            self._add([folder])

    def _remove_selected(self) -> None:
        for index in reversed(self.listbox.curselection()):
            self.listbox.delete(index)
            del self.inputs[index]

    def _clear(self) -> None:
        self.listbox.delete(0, "end")
        self.inputs.clear()

    def _pick_out_dir(self) -> None:
        folder = filedialog.askdirectory(title="Ausgabeordner wählen")
        if folder:
            self.out_dir.set(folder)

    def _pick_reference(self) -> None:
        file = filedialog.askopenfilename(
            title="Word-Vorlage wählen", filetypes=[("Word-Dokument", "*.docx")]
        )
        if file:
            self.reference.set(file)

    # ---------- Ausführung ----------

    def _write(self, text: str, tag: str | None = None) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag or ())
        self.log.see("end")
        self.log.configure(state="disabled")

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        target = self.target.get()
        files = collect_inputs(self.inputs, target, self.recursive.get())
        if not files:
            self._write(
                f"Keine Dateien gefunden, die sich nach {target} konvertieren lassen.",
                "error",
            )
            return
        options = Options(
            reference_doc=Path(self.reference.get())
            if self.reference.get().strip()
            else None,
            csv_delimiter=DELIMITERS[self.delimiter.get()],
            overwrite=self.overwrite.get(),
        )
        out_dir = Path(self.out_dir.get()) if self.out_dir.get().strip() else None

        self.button.configure(state="disabled")
        self.progress.configure(maximum=len(files), value=0)
        self._write(f"Starte: {len(files)} Datei(en) → {target}")
        self.worker = threading.Thread(
            target=self._run, args=(files, target, out_dir, options), daemon=True
        )
        self.worker.start()

    def _run(self, files, target, out_dir, options) -> None:
        failed = 0
        for src in files:
            try:
                outs = convert(src, target, out_dir, options)
                self.events.put(
                    ("ok", f"✓ {src.name} → {', '.join(o.name for o in outs)}")
                )
            except (ConversionError, ToolMissingError) as exc:
                failed += 1
                self.events.put(("error", f"✗ {src.name}: {exc}"))
            except Exception as exc:  # noqa: BLE001 # unerwartet: trotzdem weitermachen
                failed += 1
                self.events.put(("error", f"✗ {src.name}: unerwarteter Fehler: {exc}"))
            self.events.put(("step", None))
        self.events.put(("done", (len(files) - failed, len(files))))

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "step":
                    self.progress["value"] += (
                        1  # step() springt am Maximum auf 0 zurück
                    )
                elif kind == "done":
                    ok, total = payload
                    self._write(
                        f"Fertig: {ok} von {total} Dateien konvertiert.\n",
                        "ok" if ok == total else "error",
                    )
                    self.button.configure(state="normal")
                else:
                    self._write(str(payload), kind)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)


def main() -> None:
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
