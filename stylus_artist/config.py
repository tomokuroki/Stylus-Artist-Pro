from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_ROOT / "input_images"
PLANS_DIR = PROJECT_ROOT / "plans"
EXPORT_DIR = PROJECT_ROOT / "exports"


EDITOR_PROFILES = {
    "Preview only": {
        "description": "Internal preview, no external mouse control.",
        "rotate_left": "[",
        "rotate_right": "]",
        "zoom_in": "ctrl+=",
        "zoom_out": "ctrl+-",
        "pan": "space",
    },
    "Photoshop": {
        "description": "Photoshop-compatible default shortcuts.",
        "rotate_left": "r drag_left",
        "rotate_right": "r drag_right",
        "zoom_in": "ctrl+=",
        "zoom_out": "ctrl+-",
        "pan": "space",
    },
    "Krita": {
        "description": "Krita-compatible default shortcuts.",
        "rotate_left": "4",
        "rotate_right": "6",
        "zoom_in": "ctrl+=",
        "zoom_out": "ctrl+-",
        "pan": "space",
    },
    "Paint Tool SAI": {
        "description": "SAI-style basic mouse and keyboard profile.",
        "rotate_left": "delete",
        "rotate_right": "end",
        "zoom_in": "ctrl+=",
        "zoom_out": "ctrl+-",
        "pan": "space",
    },
    "Clip Studio Paint": {
        "description": "Clip Studio Paint-compatible default shortcuts.",
        "rotate_left": "-",
        "rotate_right": "^",
        "zoom_in": "ctrl+=",
        "zoom_out": "ctrl+-",
        "pan": "space",
    },
}


@dataclass
class CanvasRegion:
    x: int = 260
    y: int = 120
    width: int = 900
    height: int = 900


@dataclass
class SimulationSettings:
    realism: int = 8
    speed: int = 6
    rotation_frequency: int = 5
    sketch_passes: int = 3
    seed: int = 20260625
    output_fps: int = 30
    output_seconds: int = 45
    editor: str = "Preview only"
    dry_run: bool = True
    canvas: CanvasRegion = field(default_factory=CanvasRegion)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["editor_profile"] = EDITOR_PROFILES.get(self.editor, EDITOR_PROFILES["Preview only"])
        return data
