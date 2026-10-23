"""Kommandozeile: mdconv EINGABE... --to FORMAT"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mdconv import __version__
from mdconv.combine import CombineOptions, combine_markdown_to_pdf, find_markdown_files
from mdconv.engine import (
    ConversionError,
    Options,
    collect_inputs,
    convert,
    supported_conversions,
)
from mdconv.tools import ToolMissingError

FORMATS = sorted({f for pair in supported_conversions() for f in pair})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mdconv",
        description="Konvertiert Markdown in DOCX, HTML, PDF, XLSX, CSV und zurück.",
    )
    p.add_argument("inputs", nargs="*", type=Path, help="Dateien oder Ordner")
    p.add_argument("-t", "--to", choices=FORMATS, help="Zielformat")
    p.add_argument("-o", "--out", type=Path, help="Ausgabeordner oder Zieldatei")
    p.add_argument(
        "-r", "--recursive", action="store_true", help="Unterordner einbeziehen"
    )
    p.add_argument(
        "-c",
        "--combine",
        action="store_true",
        help="Mehrere Markdown-Dateien in ein großes PDF mit Inhaltsverzeichnis zusammenführen",
    )
    p.add_argument(
        "--title",
        default="Dokumentation",
        help="Titel für das kombinierte PDF-Dokument (Standard: Dokumentation)",
    )
    p.add_argument(
        "--author",
        default=None,
        help="Autor für das kombinierte PDF-Dokument",
    )
    p.add_argument(
        "--toc-depth",
        type=int,
        default=3,
        help="Tiefe des Inhaltsverzeichnisses beim Kombinieren (Standard: 3)",
    )
    p.add_argument(
        "--no-toc",
        action="store_true",
        help="Inhaltsverzeichnis beim Kombinieren weglassen",
    )
    p.add_argument(
        "--no-pagebreak",
        action="store_true",
        help="Seitenumbruch zwischen den Dateien weglassen",
    )
    p.add_argument(
        "-n",
        "--number-sections",
        action="store_true",
        help="Kapitel im kombinierten Dokument nummerieren",
    )
    p.add_argument(
        "--reference-doc", type=Path, help="Word-Vorlage für Formatvorlagen (MD → DOCX)"
    )
    p.add_argument(
        "--csv-delimiter",
        default=",",
        help="Trennzeichen für CSV-Ausgabe (Standard: ,)",
    )
    p.add_argument(
        "-f",
        "--overwrite",
        action="store_true",
        help="Vorhandene Dateien überschreiben",
    )
    p.add_argument(
        "--formats", action="store_true", help="Unterstützte Konvertierungen anzeigen"
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (
        sys.stdout,
        sys.stderr,
    ):  # Umlaute/Pfeile auch bei umgeleiteter Ausgabe
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.formats:
        for src, dst in supported_conversions():
            print(f"{src:>5} → {dst}")
        return 0

    if not args.inputs:
        parser.error("Mindestens eine Eingabedatei oder ein Ordner erforderlich.")

    # Combine-Modus: Mehrere Markdown-Dateien in ein PDF mit Inhaltsverzeichnis
    if args.combine:
        files = find_markdown_files(args.inputs, args.recursive)
        if not files:
            print("Keine Markdown-Dateien zum Kombinieren gefunden.", file=sys.stderr)
            return 1

        title = args.title
        # Fallback title if default: derive from first folder/file if sensible
        if title == "Dokumentation" and args.inputs:
            first_input = args.inputs[0].resolve()
            if first_input.is_dir():
                title = first_input.name or "Dokumentation"

        # Determine target PDF path
        if args.out:
            target_out = args.out.resolve()
            if target_out.is_dir() or target_out.suffix.lower() != ".pdf":
                target_out = target_out / f"{title}.pdf"
        else:
            base_dir = files[0].parent
            target_out = base_dir / f"{title}.pdf"

        combine_opt = CombineOptions(
            title=title,
            author=args.author,
            toc=not args.no_toc,
            toc_depth=args.toc_depth,
            pagebreaks=not args.no_pagebreak,
            number_sections=args.number_sections,
            overwrite=args.overwrite,
        )

        try:
            res_pdf = combine_markdown_to_pdf(files, target_out, combine_opt)
            print(
                f"OK      {len(files)} Markdown-Dateien erfolgreich kombiniert → {res_pdf}"
            )
            return 0
        except (FileExistsError, ToolMissingError, ValueError, RuntimeError) as exc:
            print(f"FEHLER  Kombinieren fehlgeschlagen: {exc}", file=sys.stderr)
            return 1

    if not args.to:
        parser.error(
            "Zielformat (--to) erforderlich (oder --combine für PDF-Zusammenführung)."
        )

    files = collect_inputs(args.inputs, args.to, args.recursive)
    if not files:
        print("Keine passenden Dateien gefunden.", file=sys.stderr)
        return 1

    options = Options(args.reference_doc, args.csv_delimiter, args.overwrite)
    failed = 0
    for src in files:
        try:
            for out in convert(src, args.to, args.out, options):
                print(f"OK      {src} → {out}")
        except (ConversionError, ToolMissingError) as exc:
            failed += 1
            print(f"FEHLER  {src}: {exc}", file=sys.stderr)

    print(f"\n{len(files) - failed} von {len(files)} Dateien konvertiert.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
