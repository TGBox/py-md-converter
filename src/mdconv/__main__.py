"""python -m mdconv: mit Argumenten CLI, ohne Argumente GUI."""

import sys


def main() -> None:
    if len(sys.argv) > 1:
        from mdconv.cli import main as cli

        sys.exit(cli())
    from mdconv.gui import main as gui

    gui()


if __name__ == "__main__":
    main()
