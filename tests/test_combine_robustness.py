"""Regression tests for the combine pipeline: one test per previously failing case."""

from __future__ import annotations

import base64
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from mdconv.combine import (
    CombineOptions,
    combine_markdown_to_pdf,
    find_combinable_files,
    safe_filename,
)

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def pdf_text(pdf: Path) -> str:
    """Extracts the text of a PDF via QtPdf or, if unavailable, pdftotext."""
    try:
        from PySide6.QtPdf import QPdfDocument

        doc = QPdfDocument()
        doc.load(str(pdf))
        text = "\n".join(doc.getAllText(i).text() for i in range(doc.pageCount()))
        doc.close()
        return text
    except ImportError:
        pass
    if shutil.which("pdftotext"):
        return subprocess.run(
            ["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True
        ).stdout
    pytest.skip("Weder PySide6.QtPdf noch pdftotext verfügbar")
    return ""


def combine(files: list[Path], tmp_path: Path, **kwargs) -> tuple[Path, list[str], str]:
    warnings: list[str] = []
    out = tmp_path / "out.pdf"
    opts = CombineOptions(overwrite=True, **kwargs)
    combine_markdown_to_pdf(files, out, opts, on_warning=warnings.append)
    return out, warnings, pdf_text(out)


def squash(text: str) -> str:
    return "".join(text.split())


# --- Fehler, die früher das ganze PDF abgebrochen haben -----------------------


def test_title_with_quotes_and_colon(tmp_path: Path):
    f = tmp_path / "a.md"
    f.write_text("# Kapitel\n\nText.", encoding="utf-8")
    _, warnings, text = combine([f], tmp_path, title='Daniels "Handbuch": Teil 1')
    assert not warnings
    assert 'Daniels "Handbuch": Teil 1' in text or "Daniels “Handbuch”: Teil 1" in text


def test_safe_filename():
    assert safe_filename('Daniels "Handbuch": Teil 1') == "Daniels _Handbuch__ Teil 1"
    assert safe_filename("a/b\\c?") == "a_b_c_"
    assert safe_filename("   ") == "Dokumentation"
    assert safe_filename("CON") == "_CON"


def test_target_pdf_is_never_an_input(tmp_path: Path):
    (tmp_path / "a.md").write_text("# A\n\nText.", encoding="utf-8")
    target = tmp_path / "Dokumentation.pdf"
    target.write_bytes(b"%PDF-1.4 alte Version")

    files = find_combinable_files([tmp_path], exclude=[target])
    assert target not in files

    # Even if the caller passes it in, it is dropped.
    combine_markdown_to_pdf(
        [tmp_path / "a.md", target], target, CombineOptions(overwrite=True)
    )
    assert target.read_bytes().startswith(b"%PDF")
    assert "alte Version" not in pdf_text(target)


def test_missing_anchor_with_umlaut_and_duplicate_ids(tmp_path: Path):
    a = tmp_path / "a.md"
    a.write_text(
        "# Übersicht {#install}\n\nSiehe [weg](#nicht-vorhanden-ä) und [hier](#install).\n",
        encoding="utf-8",
    )
    b = tmp_path / "b.md"
    b.write_text("# Nochmal {#install}\n\nSiehe [hier](#install).\n", encoding="utf-8")
    _, warnings, text = combine([a, b], tmp_path)
    assert not warnings
    assert "weg" in text and "Nochmal" in text


def test_broken_typst_in_one_file_does_not_break_others(tmp_path: Path):
    good = tmp_path / "01_gut.md"
    good.write_text("# Gut\n\nAlles in Ordnung.", encoding="utf-8")
    bad = tmp_path / "02_kaputt.md"
    bad.write_text(
        "# Kaputt\n\n```{=typst}\n#undefined-function()\n```\n", encoding="utf-8"
    )
    _, warnings, text = combine([good, bad], tmp_path)
    assert "Alles in Ordnung." in text
    assert any("02_kaputt.md" in w for w in warnings)
    assert "#undefined-function()" in text  # shown as raw text


def test_unreadable_file_becomes_note(tmp_path: Path):
    good = tmp_path / "01_gut.md"
    good.write_text("# Gut\n\nText.", encoding="utf-8")
    broken = tmp_path / "02_defekt.docx"
    broken.write_bytes(b"das ist kein Word-Dokument")
    _, warnings, text = combine([good, broken], tmp_path)
    assert any("02_defekt.docx" in w for w in warnings)
    assert "konnte nicht formatiert werden" in text


# --- Fehler, bei denen der Inhalt falsch war -----------------------------------


def test_code_is_not_mangled(tmp_path: Path):
    f = tmp_path / "code.md"
    f.write_text(
        "# Code\n\n```python\nitems[0].append(x)\n```\n\nInline `a[0].b` und *app*.jar\n",
        encoding="utf-8",
    )
    _, warnings, text = combine([f], tmp_path)
    assert not warnings
    assert "#[.]" not in text
    assert "items[0].append(x)" in text
    assert "app.jar" in squash(text)


def test_plain_text_and_logs_are_verbatim(tmp_path: Path):
    f = tmp_path / "notes.txt"
    f.write_text(
        "# kein Kapitel\n* kein Listenpunkt\nWert <tag> und $5\n", encoding="utf-8"
    )
    log = tmp_path / "app.log"
    log.write_text("ERROR x[0].y\n", encoding="utf-8")
    _, warnings, text = combine([f, log], tmp_path)
    assert not warnings
    assert "# kein Kapitel" in text
    assert "* kein Listenpunkt" in text
    assert "<tag>" in text
    assert "ERROR x[0].y" in text


def test_legacy_encoded_text(tmp_path: Path):
    f = tmp_path / "alt.txt"
    f.write_bytes("Größe und Maß".encode("cp1252"))
    _, _, text = combine([f], tmp_path)
    assert "Größe und Maß" in text


def test_code_file_containing_fence(tmp_path: Path):
    f = tmp_path / "script.py"
    f.write_text("s = '''\n```\n'''\nprint(s[0].upper())\n", encoding="utf-8")
    _, warnings, text = combine([f], tmp_path)
    assert not warnings
    assert "print(s[0].upper())" in text


def test_leading_horizontal_rule_is_not_frontmatter(tmp_path: Path):
    f = tmp_path / "hr.md"
    f.write_text("---\n\nErster Absatz.\n\n---\n\nZweiter Absatz.\n", encoding="utf-8")
    _, _, text = combine([f], tmp_path)
    assert "Erster Absatz." in text
    assert "Zweiter Absatz." in text


def test_frontmatter_title_and_broken_yaml(tmp_path: Path):
    ok = tmp_path / "01_ok.md"
    ok.write_text("---\ntitle: Titel aus YAML\n---\n\nInhalt eins.\n", encoding="utf-8")
    bad = tmp_path / "02_bad.md"
    bad.write_text("---\ntitle: [kaputt\n---\n\nInhalt zwei.\n", encoding="utf-8")
    _, warnings, text = combine([ok, bad], tmp_path)
    assert "Titel aus YAML" in text
    assert "Inhalt zwei." in text
    assert "kaputt" not in text
    assert any("02_bad.md" in w for w in warnings)


def test_image_paths_with_spaces(tmp_path: Path):
    (tmp_path / "bild mit leer.png").write_bytes(PNG_1PX)
    f = tmp_path / "bilder.md"
    f.write_text(
        "# Bilder\n\n![A](bild%20mit%20leer.png)\n\n![B](<bild mit leer.png>)\n",
        encoding="utf-8",
    )
    _, _, text = combine([f], tmp_path)
    assert "nicht gefunden" not in text


def test_raw_html_img_tag(tmp_path: Path):
    (tmp_path / "logo.png").write_bytes(PNG_1PX)
    f = tmp_path / "html.md"
    f.write_text(
        '# HTML\n\n<img src="logo.png" width="50">\n\n<img src="fehlt.png">\n',
        encoding="utf-8",
    )
    _, warnings, text = combine([f], tmp_path)
    assert not warnings
    assert "Bild nicht gefunden: fehlt.png" in text


def test_spreadsheet_cells_are_escaped(tmp_path: Path):
    f = tmp_path / "daten.csv"
    f.write_text("Name;Formel\nA|B;x*y*\n<C>;$2\n", encoding="utf-8")
    _, warnings, text = combine([f], tmp_path)
    assert not warnings
    for expected in ("A|B", "x*y*", "<C>", "$2"):
        assert expected in text


def test_word_images_are_embedded(tmp_path: Path):
    pandoc = pytest.importorskip("mdconv.tools").find_tool("pandoc")
    (tmp_path / "pic.png").write_bytes(PNG_1PX)
    src = tmp_path / "src.md"
    src.write_text("# Word\n\n![Bild](pic.png)\n", encoding="utf-8")
    for sub in ("a", "b"):
        (tmp_path / sub).mkdir()
        subprocess.run(
            [pandoc, str(src), "-o", str(tmp_path / sub / "bericht.docx")],
            cwd=tmp_path,
            check=True,
        )
    with zipfile.ZipFile(tmp_path / "a" / "bericht.docx") as z:
        assert any(n.startswith("word/media/") for n in z.namelist())

    from mdconv.combine import (
        _Build,
        _Chapter,
        _iter_nodes,
        _localize_images,
        _read_file,
    )

    build_root = tmp_path / "build"
    build = _Build(build_root, pandoc, warn=lambda _m: None)
    for index, sub in enumerate(("a", "b"), start=1):
        chapter = _Chapter(index=index, source=tmp_path / sub / "bericht.docx")
        chapter.blocks, _ = _read_file(chapter.source, index, build)
        _localize_images(chapter, build)
        images = [n for n in _iter_nodes(chapter.blocks) if n["t"] == "Image"]
        assert len(images) == 1
        assert (build_root / images[0]["c"][2][0]).is_file()

    _, warnings, _ = combine(
        [tmp_path / "a" / "bericht.docx", tmp_path / "b" / "bericht.docx"], tmp_path
    )
    assert not warnings


def test_cross_file_links(tmp_path: Path):
    a = tmp_path / "01_a.md"
    a.write_text("# A\n\n## Ziel Abschnitt\n\nText.\n", encoding="utf-8")
    b = tmp_path / "02_b.md"
    b.write_text("# B\n\nSiehe [dort](01_a.md#ziel-abschnitt).\n", encoding="utf-8")
    _, warnings, text = combine([a, b], tmp_path)
    assert not warnings
    assert "dort" in text


def test_folder_images_embedded_by_markdown_are_not_extra_chapters(tmp_path: Path):
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "screenshot.png").write_bytes(PNG_1PX)
    (tmp_path / "solo.png").write_bytes(PNG_1PX)
    (tmp_path / "doku.md").write_text(
        "# Doku\n\n![x](img/screenshot.png)\n", encoding="utf-8"
    )

    names = [f.name for f in find_combinable_files([tmp_path])]
    assert "screenshot.png" not in names
    assert "solo.png" in names

    # Explicitly selected images are always kept.
    explicit = find_combinable_files([tmp_path / "img" / "screenshot.png"])
    assert [f.name for f in explicit] == ["screenshot.png"]


def test_source_folder_stays_clean(tmp_path: Path):
    f = tmp_path / "a.md"
    f.write_text("# A\n\n![x](https://example.invalid/x.png)\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    combine_markdown_to_pdf([f], out_dir / "x.pdf", CombineOptions())
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.md", "out"]
