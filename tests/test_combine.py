"""Tests for Markdown-to-PDF combining with Table of Contents (TOC)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QImage
from PySide6.QtPdf import QPdfBookmarkModel, QPdfDocument, QPdfLinkModel

from mdconv.combine import (
    CombineOptions,
    clean_title_from_stem,
    combine_markdown_to_pdf,
    find_markdown_files,
    natural_sort_key,
    prepare_combined_markdown,
)


def test_natural_sort_key():
    files = [
        Path("ch10_advanced.md"),
        Path("ch1_intro.md"),
        Path("ch2_getting_started.md"),
        Path("ch20_appendix.md"),
    ]
    sorted_files = sorted(files, key=natural_sort_key)
    assert [f.name for f in sorted_files] == [
        "ch1_intro.md",
        "ch2_getting_started.md",
        "ch10_advanced.md",
        "ch20_appendix.md",
    ]


def test_clean_title_from_stem():
    assert clean_title_from_stem("01_intro_guide") == "Intro Guide"
    assert clean_title_from_stem("02-system-architecture") == "System Architecture"
    assert clean_title_from_stem("overview") == "Overview"
    assert clean_title_from_stem("10. FAQ") == "FAQ"


def test_find_markdown_files(tmp_path: Path):
    # Setup nested folder structure
    (tmp_path / "01_intro.md").write_text("# Intro", encoding="utf-8")
    sub1 = tmp_path / "part1"
    sub1.mkdir()
    (sub1 / "01_concept.md").write_text("# Concept", encoding="utf-8")
    (sub1 / "02_detail.markdown").write_text("# Detail", encoding="utf-8")
    (sub1 / "ignored.txt").write_text("Ignore", encoding="utf-8")

    sub2 = tmp_path / "part2"
    sub2.mkdir()
    (sub2 / "summary.md").write_text("# Summary", encoding="utf-8")

    found = find_markdown_files([tmp_path], recursive=True)
    names = [f.name for f in found]
    assert names == ["01_intro.md", "01_concept.md", "02_detail.markdown", "summary.md"]


def test_prepare_combined_markdown(tmp_path: Path):
    f1 = tmp_path / "01_intro.md"
    f1.write_text(
        "---\ntitle: 'Spezieller Intro Titel'\nauthor: Tester\n---\n\nErster Text ohne Heading.",
        encoding="utf-8",
    )
    f2 = tmp_path / "02_chapter.md"
    f2.write_text("# Zweites Kapitel\n\nInhalt Kapitel 2.", encoding="utf-8")

    opt = CombineOptions(title="Gesamtwerk")
    combined = prepare_combined_markdown([f1, f2], opt, root_dir=tmp_path)

    # Verify that f1 got an H1 heading with its frontmatter title
    assert "# Spezieller Intro Titel" in combined
    assert "Erster Text ohne Heading." in combined
    assert "# Zweites Kapitel" in combined
    assert "---" in combined  # Main doc header


def test_combine_markdown_to_pdf_with_toc_and_bookmarks(tmp_path: Path):
    # Create structured files
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    sub_dir = docs_dir / "architecture"
    sub_dir.mkdir()

    # Image in subfolder
    img_path = sub_dir / "diagram.png"
    q_img = QImage(20, 20, QImage.Format.Format_RGB32)
    q_img.fill(0x00FF00)
    q_img.save(str(img_path))

    f1 = docs_dir / "01_overview.md"
    f1.write_text("# Gesamtübersicht\n\nEinleitung in das Handbuch.", encoding="utf-8")

    f2 = sub_dir / "01_components.md"
    f2.write_text(
        "# Architekturkomponenten\n\nHier ein Schaubild:\n\n![Architektur](diagram.png)\n\n## Backend Details\n\nDetails zum Backend.",
        encoding="utf-8",
    )

    f3 = docs_dir / "03_conclusion.md"
    f3.write_text(
        "Hier steht Text ohne H1-Überschrift.\n\nUnd noch ein Absatz.",
        encoding="utf-8",
    )

    out_pdf = tmp_path / "handbuch.pdf"
    files = find_markdown_files([docs_dir], recursive=True)

    options = CombineOptions(
        title="Softwarehandbuch",
        author="Data-AL Team",
        toc=True,
        toc_depth=3,
        pagebreaks=True,
        number_sections=True,
    )

    result_pdf = combine_markdown_to_pdf(files, out_pdf, options)
    assert result_pdf.exists()
    assert result_pdf.stat().st_size > 1000

    # Validate PDF structure via PySide6 PDF
    doc = QPdfDocument()
    doc.load(str(result_pdf))
    page_count = doc.pageCount()
    assert page_count >= 4  # Cover, TOC, chapters...

    # Check bookmarks (document outline)
    model = QPdfBookmarkModel()
    model.setDocument(doc)
    assert model.rowCount() >= 3

    # Check clickable links in Table of Contents
    # The TOC is on page 1 (after cover page 0)
    link_model = QPdfLinkModel()
    link_model.setDocument(doc)
    link_model.setPage(1)
    toc_links_count = link_model.rowCount(QModelIndex())
    assert toc_links_count >= 3  # Links to the chapters

    doc.close()
