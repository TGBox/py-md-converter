# py-md-converter

Konvertiert Markdown in DOCX, HTML, PDF, XLSX und CSV – und zurück. Als Konsolenprogramm (`mdconv`) und als Fenster-Anwendung mit Drag & Drop (`mdconv-gui`).

| Von | Nach | Technik |
| --- | --- | --- |
| MD | DOCX, HTML | Pandoc |
| MD | PDF | Pandoc + Typst |
| MD (Ordner/Stapel) | Großes PDF mit Inhaltsverzeichnis | Pandoc + Typst (`--combine`) |
| DOCX, HTML | MD (GFM) | Pandoc, Bilder nach `<name>_media/` |
| MD-Tabellen | XLSX (ein Sheet je Tabelle), CSV (eine Datei je Tabelle) | eigene Logik + openpyxl |
| XLSX, CSV | MD-Tabellen | eigene Logik, CSV-Trennzeichen wird erkannt |
| PDF | MD | Docling (optional, inkl. OCR für Scans) |

## Einrichtung

```powershell
uv sync --extra gui            # Pandoc kommt über pypandoc-binary mit
uv sync --extra gui --extra pdf  # zusätzlich PDF -> MD (lädt PyTorch, groß)
```

Für **MD → PDF** wird `typst` benötigt: `typst.exe` von <https://github.com/typst/typst/releases> nach `vendor\bin\` legen (liegt bei Entwicklungsinstallation bereits vor, oder in den PATH).

## Konsole

```powershell
uv run mdconv bericht.md --to docx
uv run mdconv .\docs --to pdf -r -o .\export          # ganzer Ordner, rekursiv
uv run mdconv .\docs --to docx --reference-doc vorlage.docx
uv run mdconv tabellen.md --to csv --csv-delimiter ";"
uv run mdconv .\import --to md                         # alle DOCX/HTML/PDF/XLSX/CSV
uv run mdconv --formats                                # unterstützte Konvertierungen

# Markdown-Dateien aus Ordnerstruktur in ein großes PDF mit Inhaltsverzeichnis kombinieren:
uv run mdconv .\docs --combine -o Handbuch.pdf --title "Gesamtdokumentation"
uv run mdconv .\docs --combine -r --number-sections --toc-depth 3 -o Handbuch.pdf
```

Vorhandene Zieldateien werden nicht überschrieben, außer mit `-f/--overwrite`. Exit-Code 1, sobald eine Datei fehlschlägt.

## GUI

```powershell
uv run mdconv-gui
```

- **Dateien konvertieren**: Dateien oder Ordner per Drag & Drop in die Liste ziehen, Zielformat wählen, *Jetzt Konvertieren*.
- **In ein großes PDF kombinieren**: Bei Zielformat `PDF` die Option *Markdown-Dateien zu einem PDF kombinieren (mit Inhaltsverzeichnis)* aktivieren. Dokumenttitel, Gliederungstiefe und Nummerierung nach Wunsch anpassen.
- **Reihenfolge anpassen**: Mit den Schaltflächen *▲ Nach oben* und *▼ Nach unten* (oder per Kontextmenü) lässt sich die Reihenfolge der Kapitel vor dem Zusammenführen frei bestimmen.
- Das erzeugte PDF besitzt am Anfang ein voll klickbares Inhaltsverzeichnis sowie native PDF-Lesezeichen, über die man direkt zu den jeweiligen Dateien und Kapiteln springt.

## EXE bauen (Windows)

```powershell
.\build.ps1            # dist\mdconv.exe und dist\mdconv-gui.exe, ohne PDF-Import
.\build.ps1 -WithPdf   # mit Docling, als Ordner-Build (experimentell)
```

Das Skript kopiert Pandoc nach `vendor\bin\` und bettet alles aus diesem Ordner in die EXE ein. Werkzeuge werden in dieser Reihenfolge gesucht: Umgebungsvariable `MDCONV_PANDOC`/`MDCONV_TYPST`, eingebettet bzw. `vendor\bin`, pypandoc-binary, PATH.

## Tests

```powershell
uv run pytest
```

## Bekannte Grenzen

- Ausrichtung von Tabellenspalten (`:---:`) geht bei XLSX/CSV verloren.
- PDF → MD mit Docling lädt beim ersten Lauf Modelle aus dem Internet und ist auf der CPU langsam.
- Der `-WithPdf`-Build ist noch nicht praktisch erprobt (PyTorch + PyInstaller braucht oft Nacharbeit).
- Lizenzen bei Weitergabe beachten: Pandoc (GPL), Typst (Apache-2.0), Docling (MIT, Modelle eigene Lizenzen).

Hintergrund und Entscheidungen: [docs/ideas/py-md-converter.md](docs/ideas/py-md-converter.md)
