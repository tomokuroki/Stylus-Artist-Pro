"""PyQt6 entry point placeholder.

The project is architected so the GUI is replaceable. The current workspace
does not have PyQt6 installed, so the production entry point falls back to the
Tkinter implementation. Install PyQt6 and implement this module against the
same planner/renderer/recorder APIs to get a native Qt shell without touching
the drawing engine.
"""


def run():
    try:
        import PyQt6  # noqa: F401
    except Exception as exc:
        raise RuntimeError("PyQt6 is not installed in this Python environment.") from exc
    raise NotImplementedError("PyQt6 shell is reserved for environments with PyQt6 installed.")
