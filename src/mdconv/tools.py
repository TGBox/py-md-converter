"""Finden und Ausführen der externen Werkzeuge (Pandoc, Typst)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


class ToolMissingError(RuntimeError):
    pass


def _bundle_bin_dir() -> Path:
    # In der PyInstaller-EXE liegen die Binaries unter _MEIPASS/bin,
    # im Repo unter vendor/bin.
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "bin"
    return Path(__file__).resolve().parents[2] / "vendor" / "bin"


def find_tool(name: str) -> str:
    """Sucht ein Werkzeug: Umgebungsvariable, gebündelt, pypandoc_binary, PATH."""
    env = os.environ.get(f"MDCONV_{name.upper()}")
    if env and Path(env).is_file():
        return env

    exe = name + (".exe" if os.name == "nt" else "")
    bundled = _bundle_bin_dir() / exe
    if bundled.is_file():
        return str(bundled)

    if name == "pandoc":
        try:
            import pypandoc  # pypandoc_binary liefert pandoc mit

            path = pypandoc.get_pandoc_path()
            if path:
                p = Path(path)
                if p.is_file():
                    return str(p)
                if p.with_suffix(".exe").is_file():
                    return str(p.with_suffix(".exe"))
        except Exception:  # noqa: BLE001, S110
            pass

    found = shutil.which(name)
    if found:
        return found

    raise ToolMissingError(
        f"'{name}' wurde nicht gefunden. Lege {exe} nach vendor/bin, "
        f"setze MDCONV_{name.upper()} oder installiere es in den PATH."
    )


def run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Startet ein Werkzeug ohne Konsolenfenster und wirft bei Fehlern."""
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout).strip() or f"Exit-Code {proc.returncode}"
        raise RuntimeError(msg)
    return proc
