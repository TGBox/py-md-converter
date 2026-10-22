"""Markdown-Pipe-Tabellen lesen und schreiben."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")


@dataclass
class Table:
    title: str
    rows: list[list[str]] = field(default_factory=list)  # erste Zeile = Kopf


def _split_row(line: str) -> list[str]:
    line = line.strip()
    line = line.removeprefix("|")
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells = re.split(r"(?<!\\)\|", line)
    return [c.strip().replace("\\|", "|") for c in cells]


def parse_tables(markdown: str) -> list[Table]:
    """Findet alle Pipe-Tabellen. Titel = letzte Überschrift davor."""
    lines = markdown.splitlines()
    tables: list[Table] = []
    heading = ""
    in_code = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith(("```", "~~~")):
            in_code = not in_code
        elif not in_code:
            m = _HEADING.match(line)
            if m:
                heading = m.group(1)
            elif "|" in line and i + 1 < len(lines) and _SEP.match(lines[i + 1]):
                header = _split_row(line)
                rows = [header]
                i += 2
                while i < len(lines) and lines[i].strip() and "|" in lines[i]:
                    row = _split_row(lines[i])
                    row = (row + [""] * len(header))[: len(header)]
                    rows.append(row)
                    i += 1
                title = heading or f"Tabelle {len(tables) + 1}"
                tables.append(Table(title, rows))
                continue
        i += 1
    return tables


def cell_to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (dt.datetime, dt.date)):
        if isinstance(value, dt.datetime) and value.time() == dt.time():
            return value.date().isoformat()
        return value.isoformat()
    return str(value)


def to_markdown(rows: list[list[object]]) -> str:
    """Erzeugt eine Pipe-Tabelle; erste Zeile ist der Kopf."""
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    text = [
        [cell_to_text(c).replace("|", "\\|").replace("\n", " ") for c in r]
        for r in rows
    ]
    text = [r + [""] * (width - len(r)) for r in text]
    header, body = text[0], text[1:]
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * width) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(out)


def trim(rows: list[list[object]]) -> list[list[object]]:
    """Entfernt leere Zeilen/Spalten am Ende."""
    is_empty = lambda c: c is None or str(c).strip() == ""
    rows = [list(r) for r in rows]
    while rows and all(is_empty(c) for c in rows[-1]):
        rows.pop()
    width = max((len(r) for r in rows), default=0)
    while width and all(len(r) < width or is_empty(r[width - 1]) for r in rows):
        width -= 1
    return [r[:width] for r in rows]
