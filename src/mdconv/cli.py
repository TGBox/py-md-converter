"""Kommandozeile: mdconv EINGABE... --to FORMAT"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mdconv import __version__
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
    p.add_argument(
        "-o", "--out", type=Path, help="Ausgabeordner (Standard: neben der Quelle)"
    )
    p.add_argument(
        "-r", "--recursive", action="store_true", help="Unterordner einbeziehen"
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
    if not args.inputs or not args.to:
        parser.error("Eingabe und --to sind erforderlich.")

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
