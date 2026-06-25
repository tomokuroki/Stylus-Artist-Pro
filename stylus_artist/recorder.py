from __future__ import annotations

import json
from pathlib import Path

from .models.actions import BezierStroke, CanvasAction, DrawingPlan


def save_plan(plan: DrawingPlan, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_plan(path: str | Path) -> DrawingPlan:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    actions = []
    for item in data["actions"]:
        typ = item.pop("type")
        if typ == "stroke":
            item["points"] = [tuple(p) for p in item["points"]]
            item["color"] = tuple(item["color"])
            item["pan"] = tuple(item["pan"])
            actions.append(BezierStroke(**item))
        else:
            actions.append(CanvasAction(**item))
    return DrawingPlan(
        source_image=data["source_image"],
        width=data["width"],
        height=data["height"],
        seed=data["seed"],
        settings=data["settings"],
        actions=actions,
        analysis=data.get("analysis", {}),
    )
