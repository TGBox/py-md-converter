# py-md-converter

## Problemstellung
Wie könnten wir Inhalte zwischen Markdown und DOCX, PDF, HTML sowie XLSX/CSV in beide Richtungen konvertieren – mit erhaltener Formatierung, ganzen Ordnern auf einmal und ohne Nachdenken bei der Bedienung, per CLI wie per Doppelklick-EXE?

## Empfohlene Richtung
Eine gemeinsame **Konvertierungs-Engine** als Python-Paket, darüber zwei dünne Oberflächen: eine **CLI** (Batch, Skripte, später CI) und eine **GUI** (Drag & Drop), gebaut als Standalone-EXE per PyInstaller. Stack analog zu den bestehenden Tools: Python, uv, Tkinter, PyInstaller. Pandoc (eingebettet) übernimmt MD ↔ DOCX/HTML; für MD → PDF kommt Typst als schlanke PDF-Engine dazu. MD-Tabellen ↔ XLSX/CSV ist eigene Logik, weil Pandoc das nicht abdeckt.

**PDF → MD** ist das größte Risiko (digitale PDFs, Scans und komplexe Layouts) und wird deshalb als **eigenständiges, austauschbares Backend** gebaut: Docling als Standard (OCR, Tabellen, komplexe Layouts). Damit die Basis-EXE nicht auf GB-Größe wächst, ist der PDF-Import ein **optionales Modul**.

**Docs-as-Code** (Projektdatei, reproduzierbare Builds), der **Roundtrip-Check** und der **Zwischenablage-Modus** folgen nach dem MVP als Schichten auf derselben Engine.

## Annahmen, die geprüft werden
- [ ] Docling liefert bei echten PDFs (digital, gescannt, komplexes Layout) brauchbares Markdown – Test mit 5–10 echten PDFs.
- [ ] Docling + PyTorch lassen sich mit PyInstaller unter Windows packen, Größe ist akzeptabel – Minimal-EXE bauen.
- [ ] Docling/PyTorch laufen mit der genutzten Python-Version – `uv sync --extra pdf` in frischer Umgebung.
- [ ] Pandoc-DOCX mit Referenzvorlage sieht gut genug aus – ein echtes Dokument mit `--reference-doc` konvertieren.
- [ ] Typst-PDFs genügen optisch – dasselbe Dokument nach PDF rendern.

## MVP-Umfang
**Drin:**
- Engine: MD ↔ DOCX, MD ↔ HTML, MD → PDF, MD-Tabellen ↔ XLSX/CSV, PDF → MD (optional, Docling)
- CLI: Einzeldatei und ganzer Ordner (`mdconv ./docs --to docx`)
- GUI: Dateien/Ordner per Drag & Drop, Zielformat wählen, Fortschritt und Fehler im Klartext
- Presets: Word-Referenzvorlage pro Konvertierung wählbar

## Bewusst nicht (und warum)
- **Docs-as-Code-Projektdatei im MVP** – erst, wenn die Engine steht.
- **Roundtrip-Check im MVP** – braucht stabile Konverter in beide Richtungen.
- **Zwischenablage-Modus im MVP** – Windows-HTML-Clipboard ist Fummelei; direkt nach dem MVP.
- **Plugin-Architektur** – eine saubere Konverter-Registry reicht.
- **Ordner-Watcher** – nicht gewählt.
- **Eigener PDF-Parser** – Docling und Co. sind weit voraus.

## Entscheidungen im Verlauf
- Zielgruppe: in erster Linie der Entwickler selbst (CLI-affin).
- Pandoc darf eingebettet werden (größere EXE ok).
- PDF → MD ist kritisch, inkl. Scans und komplexer Layouts → ML-basiert (Docling).
- GUI kommt ins MVP (statt zuletzt).

## Offene Fragen (mit vorläufigen Defaults im Code)
- Ein Build mit allem oder Basis-EXE + separates PDF-Modul? → Default: Basis-EXE ohne Docling; PDF-Build per Schalter.
- Weitergabe an Kollegen? Relevant für Lizenzen (Pandoc GPL, Docling-Modelle) und Größe.
- Bilder bei DOCX/HTML → MD → Default: in Ordner `<name>_media/` neben der Ausgabe.
- Mehrere Tabellen in einer MD-Datei → Default: XLSX ein Sheet je Tabelle, CSV eine Datei je Tabelle.
