from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


StageName = Literal[
    "analysis",
    "composition",
    "rough_sketch",
    "construction",
    "line_refine",
    "color_blocking",
    "details",
    "shadows",
    "highlights",
    "polish",
    "region_finish",
    "pixel_finish",
]


@dataclass
class BezierStroke:
    id: int
    stage: StageName
    layer: str
    points: list[tuple[float, float]]
    color: tuple[int, int, int, int]
    brush_size: float
    opacity: float
    pressure: list[float]
    duration_ms: int
    pause_after_ms: int
    canvas_rotation: float = 0.0
    canvas_zoom: float = 1.0
    pan: tuple[float, float] = (0.0, 0.0)
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CanvasAction:
    id: int
    stage: StageName
    action: str
    value: float
    duration_ms: int
    pause_after_ms: int
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


PlanAction = BezierStroke | CanvasAction


@dataclass
class DrawingPlan:
    source_image: str
    width: int
    height: int
    seed: int
    settings: dict
    actions: list[PlanAction]
    analysis: dict

    def to_dict(self) -> dict:
        return {
            "source_image": self.source_image,
            "width": self.width,
            "height": self.height,
            "seed": self.seed,
            "settings": self.settings,
            "analysis": self.analysis,
            "actions": [
                {"type": "stroke", **a.to_dict()} if isinstance(a, BezierStroke) else {"type": "canvas", **a.to_dict()}
                for a in self.actions
            ],
        }
