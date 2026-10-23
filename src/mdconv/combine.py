"""Combine multiple files into a single PDF with a clickable table of contents (TOC).

Pipeline:

1. Every input file is read *separately* into a Pandoc AST (JSON). Plain text,
   logs and source code never go through a Markdown parser; they become code
   blocks directly.
2. Each AST is normalised: anchor ids get a per-file prefix (no collisions
   between files), internal and cross-file links are resolved or unwrapped,
   and every image is copied into a private build folder.
3. All ASTs are merged into one document. Pandoc renders it as Typst and
   Typst compiles it to PDF.
4. If Typst fails, the error is mapped back to the source file. That file is
   replaced by a plain-text fallback and the build is retried, so a single bad
   file never breaks the whole PDF.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mdconv.tools import ToolMissingError, find_tool, run

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


MARKDOWN_EXTENSIONS: set[str] = {".md", ".markdown"}
PANDOC_DOC_FORMATS: dict[str, str] = {
    ".docx": "docx",
    ".odt": "odt",
    ".html": "html",
    ".htm": "html",
    ".rst": "rst",
}
IMAGE_EXTENSIONS: set[str] = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
# Image formats Typst can embed (PDF pages are supported since Typst 0.14).
TYPST_IMAGE_EXTENSIONS: set[str] = IMAGE_EXTENSIONS | {".pdf"}

CODE_LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".xml": "xml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "ini",
    ".sh": "bash",
    ".bash": "bash",
    ".bat": "bat",
    ".cmd": "bat",
    ".ps1": "powershell",
    ".sql": "sql",
    ".css": "css",
    ".scss": "scss",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".rs": "rust",
    ".go": "go",
    ".php": "php",
    ".rb": "ruby",
    ".r": "r",
}

COMBINABLE_EXTENSIONS: set[str] = (
    MARKDOWN_EXTENSIONS
    | set(PANDOC_DOC_FORMATS)
    | {".xlsx", ".csv", ".tsv", ".pdf", ".txt", ".log"}
    | set(CODE_LANG_MAP)
    | IMAGE_EXTENSIONS
)

IGNORE_DIR_NAMES: set[str] = {
    ".git",
    ".svn",
    ".hg",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".idea",
    ".vscode",
    "node_modules",
}

_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


@dataclass
class CombineOptions:
    """Options for merging multiple Markdown and document files into a single PDF document."""

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


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def is_combinable_file(path: Path) -> bool:
    """Checks whether a file can be incorporated into the combined PDF."""
    if not path.is_file():
        return False
    name = path.name
    if name.startswith((".", "~$")) or name.endswith("~"):
        return False
    for parent in path.parents:
        if parent.name in IGNORE_DIR_NAMES:
            return False
    return path.suffix.lower() in COMBINABLE_EXTENSIONS


def natural_sort_key(path: Path) -> list[int | str]:
    """Provides a natural alphanumeric sort key (e.g. 'part2' comes before 'part10')."""
    parts: list[int | str] = []
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
        if p.is_file() and p.suffix.lower() in MARKDOWN_EXTENSIONS:
            found.append(p)
        elif p.is_dir():
            pattern = "**/*" if recursive else "*"
            for item in p.glob(pattern):
                if item.is_file() and item.suffix.lower() in MARKDOWN_EXTENSIONS:
                    found.append(item.resolve())

    unique = list(dict.fromkeys(found))
    unique.sort(key=natural_sort_key)
    return unique


_MD_IMAGE_REF = re.compile(r"!\[[^\]]*\]\(\s*<?([^)>]+?)>?(?:\s+[\"'][^)]*)?\s*\)")
_HTML_IMAGE_REF = re.compile(
    r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE
)


def _referenced_local_files(documents: Iterable[Path]) -> set[Path]:
    """Returns all local files referenced as images from Markdown/HTML documents."""
    referenced: set[Path] = set()
    for doc in documents:
        if doc.suffix.lower() not in MARKDOWN_EXTENSIONS | {".html", ".htm"}:
            continue
        try:
            text = doc.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in (*_MD_IMAGE_REF.finditer(text), *_HTML_IMAGE_REF.finditer(text)):
            target = _resolve_local_path(match.group(1), doc.parent)
            if target is not None:
                referenced.add(target)
    return referenced


def find_combinable_files(
    paths: Iterable[Path],
    recursive: bool = True,
    exclude: Iterable[Path] = (),
) -> list[Path]:
    """Collects and naturally sorts all combinable files from the given paths and folders.

    Images found while scanning a folder are skipped if a collected document already
    embeds them (otherwise every screenshot would become its own chapter). Explicitly
    selected files are always kept. Paths in ``exclude`` (e.g. the target PDF) are dropped.
    """
    explicit: list[Path] = []
    scanned: list[Path] = []
    for raw in paths:
        p = Path(raw).resolve()
        if is_combinable_file(p):
            explicit.append(p)
        elif p.is_dir():
            pattern = "**/*" if recursive else "*"
            scanned.extend(
                item.resolve() for item in p.glob(pattern) if is_combinable_file(item)
            )

    excluded = {Path(e).resolve() for e in exclude}
    candidates = [f for f in dict.fromkeys(explicit + scanned) if f not in excluded]

    scanned_images = {
        f for f in scanned if f.suffix.lower() in IMAGE_EXTENSIONS and f not in explicit
    }
    if scanned_images:
        embedded = _referenced_local_files(candidates)
        candidates = [f for f in candidates if f not in (scanned_images & embedded)]

    candidates.sort(key=natural_sort_key)
    return candidates


def safe_filename(title: str, fallback: str = "Dokumentation") -> str:
    """Turns a document title into a valid Windows/Unix file name (without extension)."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip().rstrip(". ")
    if not name:
        name = fallback
    if name.split(".")[0].upper() in _WINDOWS_RESERVED_NAMES:
        name = f"_{name}"
    return name[:150]


def clean_title_from_stem(stem: str) -> str:
    """Derives a human-readable title from a file stem (e.g. '01_intro_guide' -> 'Intro Guide')."""
    cleaned = re.sub(r"^\d+[\s_.-]+", "", stem)
    cleaned = re.sub(r"[_-]+", " ", cleaned).strip()
    if not cleaned:
        cleaned = stem
    if cleaned.islower():
        cleaned = cleaned.title()
    return cleaned


# ---------------------------------------------------------------------------
# Small helpers: text, paths, images
# ---------------------------------------------------------------------------


def _display_name(path: Path) -> str:
    """Short but unambiguous name for messages, e.g. 'rechnung-svc/README.md'."""
    return f"{path.parent.name}/{path.name}" if path.parent.name else path.name


def _read_text(path: Path) -> str:
    """Reads a text file as UTF-8, falling back to Windows-1252 for legacy files."""
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _resolve_local_path(src: str, base_dir: Path) -> Path | None:
    """Resolves an image/link target to an existing local file, or None."""
    src = src.strip()
    if not src or src.startswith(("#", "data:", "mailto:")):
        return None
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]+://", src) and not src.startswith("file:"):
        return None
    if src.startswith("file:"):
        src = urllib.parse.urlparse(src).path
        if re.match(r"^/[a-zA-Z]:", src):  # file:///C:/...
            src = src[1:]
    clean = src.split("?")[0].split("#")[0]
    for variant in dict.fromkeys((clean, urllib.parse.unquote(clean))):
        candidate = Path(variant)
        if not candidate.is_absolute() and not re.match(r"^[a-zA-Z]:[\\/]", variant):
            candidate = base_dir / variant
        try:
            resolved = candidate.resolve()
            if resolved.is_file():
                return resolved
        except (OSError, ValueError):
            continue
    return None


def _get_pdf_page_count(path: Path) -> int:
    """Returns number of pages in a PDF document using PySide6 or regex fallback."""
    try:
        import gc

        from PySide6.QtPdf import QPdfDocument

        doc = QPdfDocument()
        doc.load(str(path))
        count = doc.pageCount()
        doc.close()
        del doc
        gc.collect()
        if count > 0:
            return count
    except (ImportError, RuntimeError, OSError, ValueError):
        pass

    try:
        data = path.read_bytes()
        found_pages = len(re.findall(rb"/Type\s*/Page\b(?!s)", data))
        return max(found_pages, 1)
    except (OSError, ValueError):
        return 1


def _detect_image_extension(data: bytes, url_or_name: str) -> str | None:
    """Detects supported image extension (.png, .jpg, .gif, .svg) from magic bytes or URL."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"

    snippet = data[:2048].lstrip()
    if snippet.startswith(b"<svg") or (b"<?xml" in snippet and b"<svg" in snippet):
        return ".svg"

    clean = url_or_name.split("?")[0].split("#")[0].lower()
    for ext in (".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp"):
        if clean.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return None


# ---------------------------------------------------------------------------
# Pandoc AST helpers (pandoc JSON format)
# ---------------------------------------------------------------------------

Node = dict[str, Any]

# Node types whose attributes (id, classes, key-values) live at c[0]; Header has them at c[1].
_ATTR_AT_0 = {"Div", "Span", "CodeBlock", "Code", "Image", "Link", "Table", "Figure"}


def _attr_of(node: Node) -> list[Any] | None:
    t = node.get("t")
    c = node.get("c")
    if t == "Header":
        return c[1]
    if t in _ATTR_AT_0:
        return c[0]
    return None


def _inlines(text: str) -> list[Node]:
    out: list[Node] = []
    for i, word in enumerate(text.split()):
        if i:
            out.append({"t": "Space"})
        out.append({"t": "Str", "c": word})
    return out


def _para(text: str, emph: bool = False) -> Node:
    content = _inlines(text)
    if emph:
        content = [{"t": "Emph", "c": content}]
    return {"t": "Para", "c": content}


def _header(level: int, text: str, ident: str = "") -> Node:
    return {"t": "Header", "c": [level, [ident, [], []], _inlines(text)]}


def _code_block(text: str, lang: str | None = None) -> Node:
    return {"t": "CodeBlock", "c": [["", [lang] if lang else [], []], text]}


def _raw_typst(text: str) -> Node:
    return {"t": "RawBlock", "c": ["typst", text]}


def _stringify(node: Any) -> str:
    """Plain text of an AST fragment (like pandoc.utils.stringify)."""
    if isinstance(node, list):
        return "".join(_stringify(n) for n in node)
    if isinstance(node, dict):
        t = node.get("t")
        if t in {"Str", "MetaString"}:
            return node["c"]
        if t in {"Space", "SoftBreak", "LineBreak"}:
            return " "
        if t == "Code":
            return node["c"][1]
        return _stringify(node.get("c", []))
    return ""


def _transform(node: Any, fn: Callable[[Node], Node]) -> Any:
    """Walks the AST; ``fn`` may return a replacement node (which is not walked again)."""
    if isinstance(node, list):
        return [_transform(x, fn) for x in node]
    if isinstance(node, dict):
        if "t" in node:
            new = fn(node)
            if new is not node:
                return new
            if "c" in node:
                node["c"] = _transform(node["c"], fn)
            return node
        return {k: _transform(v, fn) for k, v in node.items()}
    return node


def _iter_nodes(node: Any):
    if isinstance(node, list):
        for x in node:
            yield from _iter_nodes(x)
    elif isinstance(node, dict):
        if "t" in node:
            yield node
        for v in node.values():
            yield from _iter_nodes(v)


def _normalize_anchor(anchor: str) -> str:
    """Loose anchor form so GitHub/GitLab-style anchors match Pandoc ids."""
    s = re.sub(r"-+", "-", anchor.lower()).strip("-")
    return re.sub(r"^\d+-*", "", s)


# ---------------------------------------------------------------------------
# Build context
# ---------------------------------------------------------------------------


@dataclass
class _Chapter:
    index: int
    source: Path
    blocks: list[Node] = field(default_factory=list)
    ids: dict[str, str] = field(default_factory=dict)  # original id -> prefixed id
    norm_ids: dict[str, str] = field(default_factory=dict)  # normalised -> prefixed
    anchor: str = ""  # id of the chapter heading


class _Build:
    """Holds the private build folder and the copies of all embedded assets."""

    def __init__(self, root: Path, pandoc: str, warn: Callable[[str], None]) -> None:
        self.root = root
        self.assets = root / "assets"
        self.assets.mkdir(parents=True, exist_ok=True)
        self.pandoc = pandoc
        self.warn = warn
        self.api_version: list[int] | None = None
        self._copies: dict[Path, str] = {}
        self._remote: dict[str, str | None] = {}
        self._counter = 0

    def asset(self, src: Path) -> str:
        """Copies a local file into the build folder; returns its root-relative path."""
        if src in self._copies:
            return self._copies[src]
        digest = hashlib.sha256(str(src).encode("utf-8")).hexdigest()[:12]
        dest = self.assets / f"{digest}{src.suffix.lower()}"
        shutil.copy2(src, dest)
        rel = dest.relative_to(self.root).as_posix()
        self._copies[src] = rel
        return rel

    def remote_image(self, url: str) -> str | None:
        """Downloads a remote image once; returns its root-relative path or None."""
        if url in self._remote:
            return self._remote[url]
        rel: str | None = None
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) mdconv",
                    "Accept": "image/*,*/*;q=0.8",
                },
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = resp.read(25 * 1024 * 1024)
            ext = _detect_image_extension(data, url)
            if ext:
                digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
                dest = self.assets / f"web_{digest}{ext}"
                dest.write_bytes(data)
                rel = dest.relative_to(self.root).as_posix()
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            rel = None
        self._remote[url] = rel
        return rel

    def data_uri_image(self, uri: str) -> str | None:
        match = re.match(r"^data:image/([a-zA-Z0-9+.-]+);base64,(.+)$", uri, re.DOTALL)
        if not match:
            return None
        ext = {
            "png": ".png",
            "jpeg": ".jpg",
            "jpg": ".jpg",
            "gif": ".gif",
            "svg+xml": ".svg",
            "webp": ".webp",
        }.get(match.group(1).lower())
        if not ext:
            return None
        try:
            data = base64.b64decode(match.group(2))
        except ValueError:
            return None
        self._counter += 1
        dest = self.assets / f"data_{self._counter}{ext}"
        dest.write_bytes(data)
        return dest.relative_to(self.root).as_posix()

    def pandoc_blocks(
        self, src: Path, fmt: str, extra: list[str] | None = None
    ) -> tuple[list[Node], dict[str, Any]]:
        """Reads a file with Pandoc and returns (blocks, meta)."""
        args = [self.pandoc, "-f", fmt, "-t", "json", *(extra or []), str(src)]
        proc = run(args, cwd=src.parent)
        doc = json.loads(proc.stdout)
        self.api_version = self.api_version or doc.get("pandoc-api-version")
        return doc.get("blocks", []), doc.get("meta", {})

    def markdown_blocks(self, text: str) -> list[Node]:
        """Parses a Markdown snippet produced by this module (tables, Docling output)."""
        self._counter += 1
        tmp = self.root / f"snippet_{self._counter}.md"
        tmp.write_text(text, encoding="utf-8")
        blocks, _ = self.pandoc_blocks(tmp, "markdown-citations-yaml_metadata_block")
        return blocks


# ---------------------------------------------------------------------------
# Reading single files into AST blocks
# ---------------------------------------------------------------------------

_FRONTMATTER_PATTERN = re.compile(
    r"^---[ \t]*\r?\n(.*?)\r?\n(?:---|\.\.\.)[ \t]*\r?\n?", re.DOTALL
)
_MD_ESCAPE = re.compile(r"([\\`*_\[\]<>$#~^@{}])")


def _escape_cell(value: object) -> str:
    from mdconv import tables

    return _MD_ESCAPE.sub(r"\\\1", tables.cell_to_text(value))


def _table_markdown(rows: list[list[object]]) -> str:
    from mdconv import tables

    return tables.to_markdown([[_escape_cell(c) for c in r] for r in rows])


def _read_markdown(path: Path, build: _Build) -> tuple[list[Node], str | None]:
    fmt = "markdown-citations"
    try:
        blocks, meta = build.pandoc_blocks(path, fmt)
    except RuntimeError:
        # Usually broken YAML front matter: drop it and read the rest as plain Markdown.
        text = _read_text(path)
        match = _FRONTMATTER_PATTERN.match(text)
        if match:
            text = text[match.end() :]
        build.warn(
            f"{_display_name(path)}: Kopfdaten (YAML) fehlerhaft – wurden ignoriert."
        )
        return build.markdown_blocks(text), None
    title = _stringify(meta.get("title")) or None
    return blocks, title


def _read_spreadsheet(path: Path, build: _Build) -> list[Node]:
    from mdconv import tables

    ext = path.suffix.lower()
    if ext == ".xlsx":
        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True, data_only=True)
        try:
            blocks: list[Node] = []
            for ws in wb.worksheets:
                rows = tables.trim([list(r) for r in ws.iter_rows(values_only=True)])
                if rows:
                    blocks.append(_header(2, ws.title))
                    blocks.extend(build.markdown_blocks(_table_markdown(rows)))
        finally:
            wb.close()
        return blocks or [_para("[Arbeitsmappe enthält keine Daten]", emph=True)]

    text = _read_text(path)
    lines = text.splitlines()
    if ext == ".tsv":
        rows = list(csv.reader(lines, delimiter="\t"))
    else:
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
            rows = list(csv.reader(lines, dialect))
        except csv.Error:
            rows = list(csv.reader(lines))
    rows = tables.trim(rows)
    if not rows:
        return [_para("[Tabelle ist leer]", emph=True)]
    return build.markdown_blocks(_table_markdown(rows))


def _read_pdf(path: Path, build: _Build) -> list[Node]:
    try:
        import importlib

        docling_dc = importlib.import_module("docling.document_converter")
        converter = docling_dc.DocumentConverter()
        markdown = converter.convert(path).document.export_to_markdown()
        return build.markdown_blocks(markdown)
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001 - Docling can raise anything; embed pages instead
        build.warn(
            f"{_display_name(path)}: Texterkennung fehlgeschlagen ({exc}) – Seiten werden als Bild eingebettet."
        )

    rel = build.asset(path)
    pages = _get_pdf_page_count(path)
    cmds = [f'#image("{rel}", page: {p}, width: 100%)' for p in range(1, pages + 1)]
    return [_raw_typst("\n#pagebreak()\n".join(cmds))]


def _read_file(path: Path, index: int, build: _Build) -> tuple[list[Node], str | None]:
    """Returns (blocks, title from metadata) for one input file."""
    ext = path.suffix.lower()
    if ext in MARKDOWN_EXTENSIONS:
        return _read_markdown(path, build)
    if ext in PANDOC_DOC_FORMATS:
        extra: list[str] = []
        if ext in {".docx", ".odt"}:
            extra.append(f"--extract-media={build.root / 'media' / f'f{index}'}")
        blocks, meta = build.pandoc_blocks(path, PANDOC_DOC_FORMATS[ext], extra)
        return blocks, _stringify(meta.get("title")) or None
    if ext in {".xlsx", ".csv", ".tsv"}:
        return _read_spreadsheet(path, build), None
    if ext == ".pdf":
        return _read_pdf(path, build), None
    if ext in IMAGE_EXTENSIONS:
        alt = _inlines(clean_title_from_stem(path.stem))
        image = {"t": "Image", "c": [["", [], []], alt, [path.as_posix(), ""]]}
        return [{"t": "Para", "c": [image]}], None
    if ext in CODE_LANG_MAP:
        return [_code_block(_read_text(path), CODE_LANG_MAP[ext])], None
    # .txt, .log and anything else: verbatim, never interpreted as Markdown
    return [_code_block(_read_text(path))], None


def _fallback_blocks(path: Path, reason: str) -> list[Node]:
    """Content used when a file cannot be converted: a note plus its raw text."""
    blocks = [
        _para(f"[Diese Datei konnte nicht formatiert werden: {reason}]", emph=True)
    ]
    if path.suffix.lower() in MARKDOWN_EXTENSIONS | set(CODE_LANG_MAP) | {
        ".txt",
        ".log",
        ".csv",
        ".tsv",
        ".html",
        ".htm",
        ".rst",
    }:
        try:
            blocks.append(_code_block(_read_text(path)))
        except OSError:
            pass
    return blocks


# ---------------------------------------------------------------------------
# Normalising chapters: images, ids, links
# ---------------------------------------------------------------------------

_RAW_IMG = re.compile(r"^\s*<img\b[^>]*>\s*$", re.IGNORECASE)
_RAW_IMG_SRC = re.compile(r"\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
_RAW_IMG_ALT = re.compile(r"\balt\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)


def _localize_images(chapter: _Chapter, build: _Build) -> None:
    """Points every image at a copy inside the build folder (or replaces it by text)."""
    base_dir = chapter.source.parent

    def fix(node: Node) -> Node:
        t = node["t"]
        if t in {"RawInline", "RawBlock"} and node["c"][0] == "html":
            raw = node["c"][1]
            src = _RAW_IMG_SRC.search(raw)
            if not (_RAW_IMG.match(raw) and src):
                return node
            alt = _RAW_IMG_ALT.search(raw)
            image = {
                "t": "Image",
                "c": [
                    ["", [], []],
                    _inlines(alt.group(1) if alt else ""),
                    [src.group(1), ""],
                ],
            }
            image = fix(image)
            return {"t": "Para", "c": [image]} if t == "RawBlock" else image
        if t != "Image":
            return node

        url = node["c"][2][0].strip()
        alt_text = _stringify(node["c"][1]) or "Bild"
        if url.startswith(("http://", "https://")):
            rel = build.remote_image(url)
            if rel is None:
                return {
                    "t": "Link",
                    "c": [["", [], []], node["c"][1] or _inlines(alt_text), [url, ""]],
                }
        elif url.startswith("data:"):
            rel = build.data_uri_image(url)
            if rel is None:
                return {"t": "Emph", "c": _inlines(f"[Bild: {alt_text}]")}
        else:
            local = _resolve_local_path(url, base_dir)
            if local is None:
                return {"t": "Emph", "c": _inlines(f"[Bild nicht gefunden: {url}]")}
            if local.suffix.lower() not in TYPST_IMAGE_EXTENSIONS:
                return {
                    "t": "Emph",
                    "c": _inlines(f"[Bildformat nicht unterstützt: {local.name}]"),
                }
            rel = build.asset(local)
        node["c"][2] = [rel, node["c"][2][1]]
        return node

    chapter.blocks = _transform(chapter.blocks, fix)

    def drop_empty_figures(node: Node) -> Node:
        # A figure whose image could not be embedded would only show a dangling caption.
        if node["t"] == "Figure" and not any(
            n.get("t") == "Image" for n in _iter_nodes(node["c"][2])
        ):
            return {"t": "Div", "c": [node["c"][0], node["c"][2]]}
        return node

    chapter.blocks = _transform(chapter.blocks, drop_empty_figures)


def _assign_ids(chapter: _Chapter) -> None:
    """Prefixes all ids with the chapter index so they are unique across files."""
    prefix = f"f{chapter.index}-"
    used: set[str] = set()
    for node in _iter_nodes(chapter.blocks):
        attr = _attr_of(node)
        if attr is None or not attr[0]:
            continue
        original = attr[0]
        new = prefix + original
        n = 2
        while new in used:
            new = f"{prefix}{original}-{n}"
            n += 1
        used.add(new)
        attr[0] = new
        chapter.ids.setdefault(original, new)
        chapter.norm_ids.setdefault(_normalize_anchor(original), new)

    # The chapter anchor (target of links to this file) must be read *after* prefixing.
    first_header = next((b for b in chapter.blocks if b.get("t") == "Header"), None)
    chapter.anchor = first_header["c"][1][0] if first_header is not None else ""


def _ensure_chapter_heading(
    chapter: _Chapter, meta_title: str | None, options: CombineOptions
) -> None:
    has_h1 = any(b.get("t") == "Header" and b["c"][0] == 1 for b in chapter.blocks)
    if not has_h1 and options.auto_headings:
        title = meta_title or clean_title_from_stem(chapter.source.stem)
        chapter.blocks.insert(0, _header(1, title))
    first_header = next((b for b in chapter.blocks if b.get("t") == "Header"), None)
    if first_header is not None and not first_header["c"][1][0]:
        first_header["c"][1][0] = "file"  # gets the chapter prefix in _assign_ids


def _resolve_links(chapters: list[_Chapter]) -> None:
    """Rewrites internal and cross-file links; unresolvable anchors become plain text."""
    by_path = {c.source: c for c in chapters}

    def lookup(chapter: _Chapter, anchor: str) -> str | None:
        anchor = urllib.parse.unquote(anchor)
        if anchor in chapter.ids:
            return chapter.ids[anchor]
        return chapter.norm_ids.get(_normalize_anchor(anchor))

    for chapter in chapters:

        def fix(node: Node, chapter: _Chapter = chapter) -> Node:
            if node["t"] != "Link":
                return node
            url = node["c"][2][0]
            target: str | None
            if url.startswith("#"):
                anchor = url[1:]
                target = lookup(chapter, anchor)
                if target is None:
                    for other in chapters:
                        target = lookup(other, anchor)
                        if target:
                            break
                if target is None:
                    return {"t": "Span", "c": [["", [], []], node["c"][1]]}
            else:
                path_part, _, frag = url.partition("#")
                local = (
                    _resolve_local_path(path_part, chapter.source.parent)
                    if path_part
                    else None
                )
                other = by_path.get(local) if local else None
                if other is None:
                    return node
                target = (lookup(other, frag) if frag else None) or other.anchor
                if not target:
                    return node
            node["c"][2] = ["#" + target, node["c"][2][1]]
            return node

        chapter.blocks = _transform(chapter.blocks, fix)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

# Inline elements that Pandoc renders as Typst function calls (e.g. #emph[...]).
_TYPST_CALL_INLINES = {
    "Emph",
    "Strong",
    "Strikeout",
    "Superscript",
    "Subscript",
    "SmallCaps",
    "Underline",
    "Link",
    "Image",
    "Note",
}


def _escape_field_access(node: Any) -> None:
    """Prevents ``#emph[app].jar`` being read by Typst as field access ``.jar``.

    Pandoc does not escape a dot that directly follows such a call, so the dot is
    emitted as a Typst escape (``\\.``) instead.
    """
    if isinstance(node, dict):
        for value in node.values():
            _escape_field_access(value)
        return
    if not isinstance(node, list):
        return
    i = 1
    while i < len(node):
        prev, cur = node[i - 1], node[i]
        if (
            isinstance(prev, dict)
            and isinstance(cur, dict)
            and prev.get("t") in _TYPST_CALL_INLINES
            and cur.get("t") == "Str"
            and cur["c"].startswith(".")
        ):
            node[i] = {"t": "RawInline", "c": ["typst", "\\."]}
            rest = cur["c"][1:]
            if rest:
                node.insert(i + 1, {"t": "Str", "c": rest})
        i += 1
    for item in node:
        _escape_field_access(item)


_MARKER = "// mdconv-file: {}"
_MARKER_RE = re.compile(r"^// mdconv-file: (\d+)\s*$")
_TYPST_ERROR_LINE = re.compile(r"\.typ:(\d+):\d+")


def _document_json(
    chapters: list[_Chapter], options: CombineOptions, build: _Build
) -> str:
    meta: dict[str, Any] = {
        "title": {"t": "MetaInlines", "c": _inlines(options.title)},
        "lang": {"t": "MetaString", "c": "de"},
        "papersize": {"t": "MetaString", "c": options.paper_size},
    }
    if options.author:
        meta["author"] = {
            "t": "MetaList",
            "c": [{"t": "MetaInlines", "c": _inlines(options.author)}],
        }
    if options.date:
        meta["date"] = {"t": "MetaInlines", "c": _inlines(options.date)}

    blocks: list[Node] = []
    for chapter in chapters:
        blocks.append(_raw_typst(_MARKER.format(chapter.index)))
        blocks.extend(chapter.blocks)
    doc = {
        "pandoc-api-version": build.api_version or [1, 23, 1],
        "meta": meta,
        "blocks": blocks,
    }
    return json.dumps(doc, ensure_ascii=False)


def _failing_chapter(typ_text: str, error: str) -> int | None:
    """Maps a Typst error (line number in the .typ file) back to the chapter index."""
    lines = typ_text.splitlines()
    start = error.find("error:")
    for match in _TYPST_ERROR_LINE.finditer(error, max(start, 0)):
        line_no = int(match.group(1))
        for line in reversed(lines[: line_no - 1]):
            marker = _MARKER_RE.match(line)
            if marker:
                return int(marker.group(1))
    return None


def _first_error_line(error: str) -> str:
    for line in error.splitlines():
        if line.strip().startswith("error:"):
            return line.strip().removeprefix("error:").strip()
    return error.strip().splitlines()[0] if error.strip() else "unbekannter Fehler"


def combine_markdown_to_pdf(
    files: list[Path],
    out_file: Path,
    options: CombineOptions | None = None,
    on_warning: Callable[[str], None] | None = None,
) -> Path:
    """Combines files into a single PDF with a clickable table of contents.

    Problems with single files never abort the whole document: the affected file is
    embedded as plain text and a message is passed to ``on_warning``.
    """
    opt = options or CombineOptions()
    out_file = Path(out_file).resolve()
    warn = on_warning or (lambda _msg: None)

    files = [Path(f).resolve() for f in files]
    files = [f for f in dict.fromkeys(files) if f != out_file]
    if not files:
        raise ValueError("Keine Dateien zum Kombinieren übergeben.")

    if out_file.exists() and not opt.overwrite:
        raise FileExistsError(
            f"Zieldatei existiert bereits: {out_file.name} (Überschreiben aktivieren)"
        )
    out_file.parent.mkdir(parents=True, exist_ok=True)

    pandoc = find_tool("pandoc")
    typst = find_tool("typst")

    with tempfile.TemporaryDirectory(
        prefix="mdconv_", ignore_cleanup_errors=True
    ) as tmp:
        build = _Build(Path(tmp), pandoc, warn)

        chapters: list[_Chapter] = []
        for index, path in enumerate(files, start=1):
            chapter = _Chapter(index=index, source=path)
            meta_title: str | None = None
            try:
                chapter.blocks, meta_title = _read_file(path, index, build)
                _localize_images(chapter, build)
            except (ToolMissingError, KeyboardInterrupt):
                raise
            except Exception as exc:  # noqa: BLE001 - one bad file must not stop the rest
                reason = _first_error_line(str(exc))
                warn(
                    f"{_display_name(path)}: konnte nicht gelesen werden ({reason}) – als Rohtext übernommen."
                )
                chapter.blocks = _fallback_blocks(path, reason)
            _ensure_chapter_heading(chapter, meta_title, opt)
            _assign_ids(chapter)
            chapters.append(chapter)

        _resolve_links(chapters)
        for chapter in chapters:
            _escape_field_access(chapter.blocks)

        doc_json = build.root / "combined.json"
        typ_file = build.root / "combined.typ"
        pdf_tmp = build.root / "combined.pdf"

        pandoc_args = [
            pandoc,
            str(doc_json),
            "-f",
            "json",
            "-t",
            "typst",
            "-s",
            "-o",
            str(typ_file),
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
        typst_args = [
            typst,
            "compile",
            "--root",
            str(build.root),
            str(typ_file),
            str(pdf_tmp),
        ]

        replaced: set[int] = set()
        while True:
            doc_json.write_text(_document_json(chapters, opt, build), encoding="utf-8")
            run(pandoc_args, cwd=build.root)
            try:
                run(typst_args, cwd=build.root)
                break
            except RuntimeError as exc:
                error = str(exc)
                bad = _failing_chapter(typ_file.read_text(encoding="utf-8"), error)
                if bad is None or bad in replaced:
                    raise RuntimeError(
                        f"Typst konnte das PDF nicht erzeugen:\n{error}"
                    ) from exc
                replaced.add(bad)
                chapter = chapters[bad - 1]
                reason = _first_error_line(error)
                warn(
                    f"{_display_name(chapter.source)}: Typst-Fehler ({reason}) – Datei als Rohtext übernommen."
                )
                title = clean_title_from_stem(chapter.source.stem)
                heading = next(
                    (b for b in chapter.blocks if b.get("t") == "Header"), None
                )
                if heading is not None:
                    title = _stringify(heading["c"][2]) or title
                chapter.blocks = [
                    _header(1, title, chapter.anchor or f"f{bad}-file"),
                    *_fallback_blocks(chapter.source, reason),
                ]

        try:
            shutil.copyfile(pdf_tmp, out_file)
        except PermissionError as exc:
            raise RuntimeError(
                f"Zieldatei {out_file.name} kann nicht geschrieben werden – "
                "ist sie noch in einem PDF-Viewer geöffnet?"
            ) from exc

    return out_file


# Alias for multi-format combining
combine_files_to_pdf = combine_markdown_to_pdf
