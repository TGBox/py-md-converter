"""Combine multiple Markdown files into a single structured PDF with a clickable Table of Contents (TOC)."""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from mdconv.tools import find_tool, run

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass
class CombineOptions:
    """Options for merging multiple Markdown files into a single PDF document."""

    title: str = "Dokumentation"
    author: str | None = None
    date: str | None = None
    toc: bool = True
    toc_depth: int = 3
    pagebreaks: bool = True
    number_sections: bool = False
    paper_size: str = "a4"
    overwrite: bool = False
    auto_headings: bool = True


def natural_sort_key(path: Path) -> list[int | str]:
    """Provides a natural alphanumeric sort key (e.g. 'part2' comes before 'part10')."""
    parts: list[int | str] = []
    # Include relative path string for consistent folder + filename ordering
    for component in re.split(r"(\d+)", path.as_posix()):
        if not component:
            continue
        parts.append(int(component) if component.isdigit() else component.lower())
    return parts


def find_markdown_files(paths: Iterable[Path], recursive: bool = True) -> list[Path]:
    """Collects and naturally sorts all Markdown files from the given paths and folders."""
    found: list[Path] = []
    for raw in paths:
        p = Path(raw).resolve()
        if p.is_file() and p.suffix.lower() in {".md", ".markdown"}:
            found.append(p)
        elif p.is_dir():
            pattern = "**/*" if recursive else "*"
            for item in p.glob(pattern):
                if item.is_file() and item.suffix.lower() in {".md", ".markdown"}:
                    found.append(item.resolve())

    # Eliminate duplicates while preserving naturally sorted hierarchy
    unique = list(dict.fromkeys(found))
    unique.sort(key=natural_sort_key)
    return unique


def clean_title_from_stem(stem: str) -> str:
    """Derives a human-readable title from a file stem (e.g. '01_intro_guide' -> 'Intro Guide')."""
    # Remove leading number prefixes like "01_", "1-", "01. "
    cleaned = re.sub(r"^\d+[\s_.-]+", "", stem)
    # Replace underscores and hyphens with spaces
    cleaned = re.sub(r"[_-]+", " ", cleaned).strip()
    if not cleaned:
        cleaned = stem
    # Capitalize words if all lowercase
    if cleaned.islower():
        cleaned = cleaned.title()
    return cleaned


_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_H1_PATTERN = re.compile(r"^\s*#\s+(.+)$", re.MULTILINE)
_IMG_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _extract_title_from_frontmatter(yaml_text: str) -> str | None:
    """Extracts 'title: ...' from raw YAML frontmatter text."""
    for line in yaml_text.splitlines():
        line = line.strip()
        if line.startswith("title:"):
            raw_val = line[6:].strip().strip("\"'")
            if raw_val:
                return raw_val
    return None


def prepare_combined_markdown(
    files: list[Path],
    options: CombineOptions,
    root_dir: Path,
) -> str:
    """Merges Markdown files into a unified document with adjusted image links and chapter headings."""
    sections: list[str] = []

    # Document Header with metadata for Pandoc
    meta_lines = ["---", f'title: "{options.title}"', 'lang: "de"']
    if options.author:
        meta_lines.append(f'author: "{options.author}"')
    if options.date:
        meta_lines.append(f'date: "{options.date}"')
    meta_lines.append("---\n")
    sections.append("\n".join(meta_lines))

    for file_path in files:
        raw_text = file_path.read_text(encoding="utf-8-sig")

        # Extract & strip frontmatter
        extracted_title: str | None = None
        match = _FRONTMATTER_PATTERN.match(raw_text)
        if match:
            extracted_title = _extract_title_from_frontmatter(match.group(1))
            body = raw_text[match.end() :]
        else:
            body = raw_text

        body = body.strip()

        # Check if the file already contains an H1 heading
        has_h1 = bool(_H1_PATTERN.search(body))

        if not has_h1 and options.auto_headings:
            # Generate an H1 heading so this file appears in the Table of Contents
            heading_title = extracted_title or clean_title_from_stem(file_path.stem)
            body = f"# {heading_title}\n\n{body}"

        # Adjust relative image paths to be relative to root_dir
        def _replace_img(match_obj: re.Match, current_file: Path = file_path) -> str:
            alt = match_obj.group(1)
            src = match_obj.group(2).strip()

            # Ignore absolute paths, URLs or anchors
            if src.startswith(("http://", "https://", "data:", "#", "/")) or (
                len(src) > 1 and src[1] == ":"
            ):
                return match_obj.group(0)

            # Resolve image relative to this markdown file's directory
            img_file = (current_file.parent / src).resolve()
            try:
                # Compute path relative to root_dir
                rel_to_root = img_file.relative_to(root_dir).as_posix()
                return f"![{alt}]({rel_to_root})"
            except ValueError:
                # Fallback if image is outside root_dir
                return f"![{alt}]({img_file.as_posix()})"

        body = _IMG_PATTERN.sub(_replace_img, body)

        sections.append(body)

    return "\n\n".join(sections) + "\n"


def combine_markdown_to_pdf(
    files: list[Path],
    out_file: Path,
    options: CombineOptions | None = None,
) -> Path:
    """Combines a list of Markdown files into a single PDF with a clickable Table of Contents.

    Uses Pandoc and Typst.
    """
    if not files:
        raise ValueError("Keine Markdown-Dateien zum Kombinieren übergeben.")

    opt = options or CombineOptions()
    out_file = Path(out_file).resolve()

    if out_file.exists() and not opt.overwrite:
        raise FileExistsError(
            f"Zieldatei existiert bereits: {out_file.name} (Überschreiben aktivieren)"
        )

    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Determine common root directory for all files
    try:
        import os

        common_root = Path(os.path.commonpath([str(f.resolve().parent) for f in files]))
    except (ValueError, OSError):
        common_root = files[0].parent.resolve()

    pandoc = find_tool("pandoc")
    typst = find_tool("typst")

    temp_typ = common_root / ".mdconv_combined.typ"
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        merged_md = temp_path / "combined.md"

        # Generate unified markdown content
        content = prepare_combined_markdown(files, opt, root_dir=common_root)
        merged_md.write_text(content, encoding="utf-8")

        # Step 1: Pandoc compiles Markdown to Standalone Typst (.typ)
        pandoc_args = [
            pandoc,
            str(merged_md),
            "-s",
            "-o",
            str(temp_typ),
            "-M",
            "lang=de",
            "-M",
            f"paper={opt.paper_size}",
        ]

        if opt.toc:
            pandoc_args.extend(["--toc", f"--toc-depth={opt.toc_depth}"])

        if opt.number_sections:
            pandoc_args.append("--number-sections")

        if opt.pagebreaks:
            pandoc_args.extend(
                [
                    "-V",
                    "header-includes=#show heading.where(level: 1): it => pagebreak(weak: true) + it",
                ]
            )

        try:
            run(pandoc_args, cwd=common_root)

            # Step 2: Typst compiles .typ to PDF, resolving all images relative to common_root
            typst_args = [
                typst,
                "compile",
                "--root",
                str(common_root),
                str(temp_typ),
                str(out_file),
            ]
            run(typst_args, cwd=common_root)
        finally:
            if temp_typ.exists():
                try:
                    temp_typ.unlink()
                except OSError:
                    pass

    return out_file
