from __future__ import annotations

import argparse


def main():
    parser = argparse.ArgumentParser(description="Stylus Artist Pro")
    parser.add_argument("--qt", action="store_true", help="Use PyQt6 UI if installed.")
    args = parser.parse_args()

    if args.qt:
        try:
            from .ui.qt_app import run

            run()
            return
        except Exception as exc:
            print(f"PyQt6 UI unavailable, falling back to Tkinter: {exc}")

    from .ui.tk_app import run

    run()


if __name__ == "__main__":
    main()
