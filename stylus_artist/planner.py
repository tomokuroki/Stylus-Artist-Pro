from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from .config import SimulationSettings
from .models.actions import BezierStroke, CanvasAction, DrawingPlan, PlanAction
from .strokes import humanized_path, pressure_curve
from .vision.analysis import ImageAnalysis, analyze_image


STAGE_ORDER = [
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
]


class DrawingPlanner:
    def __init__(self, settings: SimulationSettings):
        self.settings = settings
        self.rng = random.Random(settings.seed)
        self._id = 0

    def build(self, image: Image.Image, source: str | Path) -> DrawingPlan:
        source_seed = self._source_seed(image, source)
        self.rng = random.Random(source_seed)
        analysis = analyze_image(image, self.settings.realism)
        actions: list[PlanAction] = []
        actions.extend(self._analysis_actions())
        actions.extend(self._composition_actions(analysis))
        actions.extend(self._background_actions(image, analysis))
        actions.extend(self._color_actions(image, analysis))
        actions.extend(self._shadow_actions(image, analysis))
        actions.extend(self._highlight_actions(image, analysis))
        actions.extend(self._line_actions(image, analysis))
        actions.extend(self._detail_actions(image, analysis))
        actions.extend(self._polish_actions(image, analysis))
        actions.extend(self._region_finish_actions(image, analysis))
        return DrawingPlan(
            source_image=str(source),
            width=image.width,
            height=image.height,
            seed=source_seed,
            settings=self.settings.to_dict(),
            actions=actions,
            analysis=analysis.to_dict(),
        )

    def _source_seed(self, image: Image.Image, source: str | Path) -> int:
        thumb = image.convert("RGB").resize((32, 32), Image.Resampling.BOX)
        acc = int(self.settings.seed) & 0xFFFFFFFF
        for i, (r, g, b) in enumerate(thumb.getdata()):
            acc = (acc * 1664525 + r * 3 + g * 5 + b * 7 + i * 1013904223) & 0xFFFFFFFF
        for ch in str(source).encode("utf-8", errors="ignore"):
            acc = ((acc << 5) - acc + ch) & 0xFFFFFFFF
        return acc or int(self.settings.seed)

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _canvas_action(self, stage, action, value, duration=350, pause=80, note="") -> CanvasAction:
        return CanvasAction(self._next_id(), stage, action, value, duration, pause, note)

    def _focus_actions(self, stage: str, center: tuple[float, float], zoom: float, note: str) -> list[PlanAction]:
        cx, cy = center
        return [
            self._canvas_action(stage, "focus_x", float(cx), 180, 20, note),
            self._canvas_action(stage, "focus_y", float(cy), 180, 20, note),
            self._canvas_action(stage, "zoom", float(zoom), 420, 90, note),
            self._canvas_action(stage, "rotate", self.rng.uniform(-5, 5), 380, 80, "turn canvas like a tablet artist"),
        ]

    def _stroke(
        self,
        stage,
        layer,
        start,
        end,
        color,
        brush,
        opacity,
        duration,
        pause,
        wobble,
        note="",
    ) -> BezierStroke:
        dist = math.dist(start, end)
        samples = max(12, min(96, int(dist / 5)))
        path = humanized_path(start, end, self.rng, wobble, samples)
        duration = self._human_duration(dist, duration)
        raster_layer = layer in {"base_color", "details", "shadows", "highlights", "polish", "region_finish", "pixel_finish"}
        return BezierStroke(
            id=self._next_id(),
            stage=stage,
            layer=layer,
            points=path,
            color=color,
            brush_size=max(0.8, brush),
            opacity=max(0.02, min(1.0, opacity)),
            pressure=pressure_curve(len(path), self.rng, base=max(0.15, opacity)),
            duration_ms=duration,
            pause_after_ms=pause,
            canvas_rotation=0.0 if raster_layer else self.rng.uniform(-4, 4),
            canvas_zoom=self.rng.uniform(0.90, 1.55) if raster_layer else self.rng.uniform(0.74, 1.25),
            pan=(self.rng.uniform(-0.05, 0.05), self.rng.uniform(-0.05, 0.05)),
            note=note,
        )

    def _path_stroke(
        self,
        stage,
        layer,
        points: list[tuple[float, float]],
        color,
        brush,
        opacity,
        duration,
        pause,
        note="",
    ) -> BezierStroke:
        clean = self._smooth_path(points)
        length = self._path_length(clean)
        duration = self._human_duration(length, duration)
        return BezierStroke(
            id=self._next_id(),
            stage=stage,
            layer=layer,
            points=clean,
            color=color,
            brush_size=max(0.8, brush),
            opacity=max(0.02, min(1.0, opacity)),
            pressure=pressure_curve(len(clean), self.rng, base=max(0.18, opacity)),
            duration_ms=duration,
            pause_after_ms=pause,
            canvas_rotation=0.0,
            canvas_zoom=self.rng.uniform(1.02, 1.75),
            pan=(self.rng.uniform(-0.04, 0.04), self.rng.uniform(-0.04, 0.04)),
            note=note,
        )

    def _path_length(self, points: list[tuple[float, float]]) -> float:
        return sum(math.dist(points[i - 1], points[i]) for i in range(1, len(points)))

    def _smooth_path(self, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if len(points) < 4:
            return points
        out = [points[0]]
        for i in range(1, len(points) - 1):
            px, py = points[i - 1]
            x, y = points[i]
            nx, ny = points[i + 1]
            out.append((px * 0.18 + x * 0.64 + nx * 0.18, py * 0.18 + y * 0.64 + ny * 0.18))
        out.append(points[-1])
        return out

    def _human_duration(self, distance: float, base_duration: int) -> int:
        speed_factor = max(0.35, min(1.6, self.settings.speed / 5))
        deliberate = 1.0 / speed_factor
        long_stroke_time = distance * self.rng.uniform(8.0, 15.0)
        return int(max(base_duration, long_stroke_time) * deliberate)

    def _analysis_actions(self) -> list[PlanAction]:
        return [
            self._canvas_action("analysis", "pause_observe", 1.0, 900, 250, "artist studies reference"),
            self._canvas_action("analysis", "zoom", 0.78, 420, 90, "fit canvas"),
        ]

    def _composition_actions(self, analysis: ImageAnalysis) -> list[PlanAction]:
        return [
            self._canvas_action("composition", "pause_observe", 1.0, 900, 220, "choose paint order"),
            self._canvas_action("composition", "zoom", 0.92, 460, 120, "block in full raster canvas"),
        ]

    def _background_actions(self, image, analysis: ImageAnalysis) -> list[PlanAction]:
        x1, y1, x2, y2 = self._expanded_bbox(analysis, image.width, image.height, pad=0.10)
        cell = self._paint_cell(image, fine=False)
        actions = [self._canvas_action("color_blocking", "zoom", 0.82, 420, 120, "paint background first")]
        actions.extend(
            self._digital_scan_fill(
                image,
                "color_blocking",
                "base_color",
                cell=cell,
                max_runs=2600 + self.settings.realism * 220,
                opacity=1.0,
                quantize=14,
                exclude_box=(x1, y1, x2, y2),
                note="background paint pass",
            )
        )
        return actions

    def _sketch_actions(self, image, analysis: ImageAnalysis) -> list[PlanAction]:
        actions: list[PlanAction] = []
        points = self._pick(analysis.edge_points, 180 * self.settings.sketch_passes)
        for i, (x, y, strength) in enumerate(points):
            length = self.rng.uniform(34, 96)
            angle = self._flow_angle(x, y, image.width, image.height)
            start = (x - math.cos(angle) * length, y - math.sin(angle) * length)
            end = (x + math.cos(angle) * length, y + math.sin(angle) * length)
            color = (35, 35, 35, min(155, 45 + strength))
            actions.append(self._stroke("rough_sketch", "sketch", start, end, color, self.rng.uniform(1.2, 3.2), 0.35, self.rng.randint(360, 920), self.rng.randint(40, 240), 12))
            if i % max(20, 90 - self.settings.rotation_frequency * 8) == 0:
                actions.append(self._canvas_action("rough_sketch", "rotate", self.rng.uniform(-12, 12), 520, 160))
        return actions

    def _construction_actions(self, analysis: ImageAnalysis) -> list[PlanAction]:
        actions: list[PlanAction] = [self._canvas_action("construction", "zoom", 1.08, 360, 90)]
        x1, y1, x2, y2 = analysis.composition["bbox"]
        for scale in (1.0, 0.78, 0.55):
            mx = (x2 - x1) * (1 - scale) / 2
            my = (y2 - y1) * (1 - scale) / 2
            actions.append(self._stroke("construction", "construction", (x1 + mx, y1 + my), (x2 - mx, y1 + my), (100, 80, 160, 55), 1.4, 0.22, 450, 65, 4))
            actions.append(self._stroke("construction", "construction", (x2 - mx, y1 + my), (x2 - mx, y2 - my), (100, 80, 160, 45), 1.4, 0.22, 450, 65, 4))
            actions.append(self._stroke("construction", "construction", (x1 + mx, y2 - my), (x2 - mx, y2 - my), (100, 80, 160, 42), 1.2, 0.18, 420, 45, 4, "form box"))
            actions.append(self._stroke("construction", "construction", (x1 + mx, y1 + my), (x1 + mx, y2 - my), (100, 80, 160, 38), 1.2, 0.18, 420, 45, 4, "form box"))
        cx, cy = analysis.composition["center"]
        w = max(20, (x2 - x1) * 0.24)
        h = max(20, (y2 - y1) * 0.24)
        for offset in (-0.7, 0.0, 0.7):
            yy = cy + offset * h
            actions.append(self._stroke("construction", "construction", (cx - w, yy), (cx + w, yy + self.rng.uniform(-8, 8)), (150, 95, 120, 42), 1.0, 0.18, 360, 45, 5, "anime face/detail guide"))
        return actions

    def _line_actions(self, image, analysis: ImageAnalysis) -> list[PlanAction]:
        actions: list[PlanAction] = [self._canvas_action("line_refine", "zoom", 1.25, 320, 80)]
        paths = self._trace_contour_paths(image, analysis)
        brush = max(1.6, self._paint_cell(image, fine=True) * 0.26)
        for i, path in enumerate(paths):
            alpha = 185 if i < 10 else 140
            width = brush * self.rng.uniform(0.78, 1.18)
            actions.append(
                self._path_stroke(
                    "line_refine",
                    "lineart",
                    path,
                    (16, 16, 18, alpha),
                    width,
                    0.72,
                    self.rng.randint(900, 1800),
                    self.rng.randint(80, 240),
                    note="continuous object contour",
                )
            )
            if i and i % 14 == 0:
                actions.append(self._canvas_action("line_refine", "zoom", self.rng.uniform(0.95, 1.95), 520, 120))
        return actions

    def _color_actions(self, image, analysis: ImageAnalysis) -> list[PlanAction]:
        x1, y1, x2, y2 = self._expanded_bbox(analysis, image.width, image.height, pad=0.08)
        coarse = self._paint_cell(image, fine=False)
        fine = self._paint_cell(image, fine=True)
        actions = [self._canvas_action("color_blocking", "zoom", 1.18, 420, 120, "paint main object")]
        actions.extend(
            self._digital_scan_fill(
                image,
                "color_blocking",
                "base_color",
                cell=coarse,
                max_runs=3600 + self.settings.realism * 260,
                opacity=1.0,
                quantize=12,
                include_box=(x1, y1, x2, y2),
                note="main object paint pass",
            )
        )
        actions.extend(
            self._digital_scan_fill(
                image,
                "details",
                "details",
                cell=fine,
                max_runs=4600 + self.settings.realism * 320,
                opacity=1.0,
                quantize=7,
                include_box=(x1, y1, x2, y2),
                note="fine raster paint pass",
            )
        )
        return actions

    def _detail_actions(self, image, analysis: ImageAnalysis) -> list[PlanAction]:
        actions: list[PlanAction] = []
        focus_boxes = self._focus_boxes(image, analysis, limit=6 + self.settings.realism // 2)
        for i, box in enumerate(focus_boxes):
            x1, y1, x2, y2 = box
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            actions.extend(self._focus_actions("details", (cx, cy), self.rng.uniform(1.65, 2.65), "zoom into object detail"))
            actions.extend(
                self._digital_scan_fill(
                    image,
                    "details",
                    "details",
                    cell=max(4, int(self._paint_cell(image, fine=True) * 0.75)),
                    max_runs=360 + self.settings.realism * 42,
                    opacity=1.0,
                    quantize=5,
                    include_box=box,
                    note="local detail paint",
                )
            )
            local_points = [p for p in analysis.detail_points + analysis.saliency_points if x1 <= p[0] <= x2 and y1 <= p[1] <= y2]
            for x, y, _ in self._pick(local_points, 28 + self.settings.realism * 5):
                actions.append(self._color_stroke_from_pixel(image, "details", "details", x, y, self._paint_cell(image, fine=True) * 0.55, 0.94, 1.4, exact=True))
            if i % 2 == 1:
                actions.append(self._canvas_action("details", "zoom", 0.92, 460, 140, "zoom out to compare whole image"))
        return actions

    def _shadow_actions(self, image, analysis: ImageAnalysis) -> list[PlanAction]:
        actions = [self._canvas_action("shadows", "zoom", 1.18, 300, 80)]
        for x, y, strength in self._pick(analysis.shadow_points, 360 + self.settings.realism * 70):
            r, g, b = image.getpixel((x, y))
            color = (max(0, r - 35), max(0, g - 35), max(0, b - 40), min(185, 55 + strength))
            actions.append(self._pixel_stroke("shadows", "shadows", x, y, color, self._paint_cell(image, fine=False) * 1.35, 0.42, 5))
        return actions

    def _highlight_actions(self, image, analysis: ImageAnalysis) -> list[PlanAction]:
        actions = [self._canvas_action("highlights", "zoom", 1.35, 320, 80)]
        for x, y, strength in self._pick(analysis.highlight_points, 260 + self.settings.realism * 55):
            r, g, b = image.getpixel((x, y))
            color = (min(255, r + 28), min(255, g + 28), min(255, b + 35), min(210, 70 + strength))
            actions.append(self._pixel_stroke("highlights", "highlights", x, y, color, self._paint_cell(image, fine=True) * 0.9, 0.66, 2.8))
        return actions

    def _polish_actions(self, image, analysis: ImageAnalysis) -> list[PlanAction]:
        actions = [self._canvas_action("polish", "zoom", 0.92, 420, 220, "review full image")]
        points = self._pick(analysis.saliency_points, 240 + self.settings.realism * 45)
        for x, y, _ in points:
            actions.append(self._color_stroke_from_pixel(image, "polish", "polish", x, y, self._paint_cell(image, fine=True) * 0.55, 1.0, 1.2, exact=True))
        actions.append(self._canvas_action("polish", "pause_observe", 1, 1100, 250, "final check"))
        return actions

    def _region_finish_actions(self, image, analysis: ImageAnalysis) -> list[PlanAction]:
        x1, y1, x2, y2 = self._expanded_bbox(analysis, image.width, image.height, pad=0.05)
        actions: list[PlanAction] = [
            self._canvas_action("region_finish", "zoom", 1.35, 520, 140, "final raster correction"),
        ]
        actions.extend(
            self._digital_scan_fill(
                image,
                "region_finish",
                "region_finish",
                cell=self._paint_cell(image, fine=True),
                quantize=6,
                max_runs=2600 + self.settings.realism * 180,
                opacity=1.0,
                include_box=(x1, y1, x2, y2),
                note="final clean paint pass",
            )
        )
        for x, y, _ in self._pick(analysis.detail_points + analysis.saliency_points, 420 + self.settings.realism * 90):
            actions.append(self._color_stroke_from_pixel(image, "pixel_finish", "pixel_finish", x, y, self._paint_cell(image, fine=True) * 0.42, 1.0, 0.8, exact=True))
        actions.append(self._canvas_action("region_finish", "zoom", 0.9, 520, 260, "final digital art review"))
        return actions

    def _region_fill_actions(
        self,
        image,
        stage,
        layer,
        cell: int,
        quantize: int,
        max_regions: int,
        opacity: float,
    ) -> list[PlanAction]:
        actions: list[PlanAction] = [self._canvas_action(stage, "zoom", self.rng.uniform(0.95, 1.65), 460, 120)]
        regions = self._build_color_regions(image, cell=cell, quantize=quantize)
        for region_index, region in enumerate(regions[:max_regions]):
            cells = region["cells"]
            if not cells:
                continue
            color = (*region["color"], int(255 * opacity))
            brush = max(2.0, cell * self.rng.uniform(0.78, 1.22))
            strokes = self._region_strokes(cells, cell, image.width, image.height)
            for start, end, length in strokes:
                actions.append(
                    self._stroke(
                        stage,
                        layer,
                        start,
                        end,
                        color,
                        brush,
                        opacity,
                        int(280 + length * self.rng.uniform(5.0, 11.0)),
                        self.rng.choice([15, 25, 40, 70, 110, 170]),
                        wobble=max(0.25, cell * 0.22),
                        note="region fill stroke",
                    )
                )
            if region_index and region_index % 180 == 0:
                actions.append(self._canvas_action(stage, "zoom", self.rng.uniform(1.0, 2.2), 420, 100))
                actions.append(self._canvas_action(stage, "rotate", self.rng.uniform(-9, 9), 380, 90))
        return actions

    def _build_color_regions(self, image, cell: int, quantize: int) -> list[dict]:
        cols = max(1, math.ceil(image.width / cell))
        rows = max(1, math.ceil(image.height / cell))
        keys = {}
        colors = {}
        for gy in range(rows):
            for gx in range(cols):
                x1, y1 = gx * cell, gy * cell
                x2, y2 = min(image.width, x1 + cell), min(image.height, y1 + cell)
                crop = image.crop((x1, y1, x2, y2)).resize((1, 1), Image.Resampling.BOX)
                r, g, b = crop.getpixel((0, 0))
                key = (r // quantize, g // quantize, b // quantize)
                keys[(gx, gy)] = key
                colors[(gx, gy)] = (r, g, b)

        visited = set()
        regions = []
        for gy in range(rows):
            for gx in range(cols):
                start = (gx, gy)
                if start in visited:
                    continue
                key = keys[start]
                stack = [start]
                visited.add(start)
                cells = []
                rs = gs = bs = 0
                while stack:
                    cell_pos = stack.pop()
                    cells.append(cell_pos)
                    r, g, b = colors[cell_pos]
                    rs += r
                    gs += g
                    bs += b
                    x, y = cell_pos
                    for nb in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if nb in visited or nb not in keys or keys[nb] != key:
                            continue
                        visited.add(nb)
                        stack.append(nb)
                count = max(1, len(cells))
                regions.append(
                    {
                        "cells": cells,
                        "color": (int(rs / count), int(gs / count), int(bs / count)),
                        "area": count,
                    }
                )
        regions.sort(key=lambda r: r["area"], reverse=True)
        return regions

    def _region_strokes(self, cells, cell: int, width: int, height: int):
        by_row = {}
        for gx, gy in cells:
            by_row.setdefault(gy, []).append(gx)
        rows = list(by_row.items())
        self.rng.shuffle(rows)
        strokes = []
        max_rows = max(1, min(len(rows), 1 + int(math.sqrt(len(cells)))))
        for gy, xs in rows[:max_rows]:
            xs = sorted(xs)
            runs = []
            start = prev = xs[0]
            for x in xs[1:]:
                if x == prev + 1:
                    prev = x
                else:
                    runs.append((start, prev))
                    start = prev = x
            runs.append((start, prev))
            self.rng.shuffle(runs)
            for x1, x2 in runs[:3]:
                y = gy * cell + cell * self.rng.uniform(0.30, 0.70)
                start = (max(0, x1 * cell + self.rng.uniform(0, cell * 0.35)), min(height - 1, y))
                end = (min(width - 1, (x2 + 1) * cell - self.rng.uniform(0, cell * 0.35)), min(height - 1, y + self.rng.uniform(-cell * 0.18, cell * 0.18)))
                length = max(1.0, math.dist(start, end))
                if length >= cell * 0.45:
                    strokes.append((start, end, length))
        if not strokes:
            gx, gy = cells[0]
            x = gx * cell + cell / 2
            y = gy * cell + cell / 2
            strokes.append(((x - cell * 0.35, y), (x + cell * 0.35, y + self.rng.uniform(-1, 1)), cell))
        return strokes[:8]

    def _paint_grid(self, image, stage, layer, cell, count, brush, opacity, wobble) -> list[PlanAction]:
        coords = [(x, y) for y in range(cell, image.height - cell, cell) for x in range(cell, image.width - cell, cell)]
        self.rng.shuffle(coords)
        actions: list[PlanAction] = [self._canvas_action(stage, "zoom", 0.98, 350, 80)]
        for i, (x, y) in enumerate(coords[: count + self.settings.realism * 180]):
            actions.append(self._color_stroke_from_pixel(image, stage, layer, x, y, brush, opacity, wobble))
            if i % 160 == 0:
                actions.append(self._canvas_action(stage, "rotate", self.rng.uniform(-9, 9), 260, 35))
        return actions

    def _digital_scan_fill(
        self,
        image,
        stage,
        layer,
        cell: int,
        max_runs: int,
        opacity: float,
        quantize: int = 18,
        include_box: tuple[int, int, int, int] | None = None,
        exclude_box: tuple[int, int, int, int] | None = None,
        note: str = "paint pass",
    ) -> list[PlanAction]:
        actions: list[PlanAction] = [self._canvas_action(stage, "zoom", self.rng.uniform(0.95, 1.55), 420, 110)]
        runs = []
        for y in range(cell // 2, image.height, cell):
            x = cell // 2
            while x < image.width:
                if not self._point_allowed(x, y, include_box, exclude_box):
                    x += cell
                    continue
                r, g, b = image.getpixel((min(image.width - 1, x), min(image.height - 1, y)))
                key = (r // quantize, g // quantize, b // quantize)
                start = x
                x += cell
                while x < image.width:
                    if not self._point_allowed(x, y, include_box, exclude_box):
                        break
                    rr, gg, bb = image.getpixel((min(image.width - 1, x), min(image.height - 1, y)))
                    if (rr // quantize, gg // quantize, bb // quantize) != key:
                        break
                    x += cell
                end = min(image.width - cell // 2, x)
                if end - start >= cell:
                    mid = int((start + end) / 2)
                    color = image.getpixel((min(image.width - 1, mid), min(image.height - 1, y)))
                    runs.append((start, y, end, y, (*color, int(255 * opacity)), end - start))
        runs.sort(key=lambda run: run[-1], reverse=True)
        head = runs[: max_runs // 3]
        tail = runs[max_runs // 3 :]
        self.rng.shuffle(tail)
        runs = head + tail
        for i, (x1, y1, x2, y2, color, length) in enumerate(runs[:max_runs]):
            brush = max(2.0, cell * self.rng.uniform(1.10, 1.55))
            duration = int(420 + length * self.rng.uniform(7.5, 14.0))
            pause = self.rng.choice([20, 35, 55, 85, 130, 190])
            actions.append(
                self._stroke(
                    stage,
                    layer,
                    (x1, y1 + self.rng.uniform(-0.8, 0.8)),
                    (x2, y2 + self.rng.uniform(-0.8, 0.8)),
                    color,
                    brush,
                    opacity,
                    duration,
                    pause,
                    wobble=max(0.18, cell * 0.06),
                    note=note,
                )
            )
            if i and i % 420 == 0:
                actions.append(self._canvas_action(stage, "zoom", self.rng.uniform(1.0, 2.1), 380, 90))
        return actions

    def _point_allowed(
        self,
        x: float,
        y: float,
        include_box: tuple[int, int, int, int] | None,
        exclude_box: tuple[int, int, int, int] | None,
    ) -> bool:
        if include_box is not None:
            x1, y1, x2, y2 = include_box
            if x < x1 or x > x2 or y < y1 or y > y2:
                return False
        if exclude_box is not None:
            x1, y1, x2, y2 = exclude_box
            if x1 <= x <= x2 and y1 <= y <= y2:
                return False
        return True

    def _expanded_bbox(self, analysis: ImageAnalysis, width: int, height: int, pad: float) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = analysis.composition["bbox"]
        dx = int((x2 - x1) * pad)
        dy = int((y2 - y1) * pad)
        return (max(0, x1 - dx), max(0, y1 - dy), min(width - 1, x2 + dx), min(height - 1, y2 + dy))

    def _focus_boxes(self, image, analysis: ImageAnalysis, limit: int) -> list[tuple[int, int, int, int]]:
        points = analysis.saliency_points + analysis.detail_points + analysis.highlight_points
        if not points:
            return [self._expanded_bbox(analysis, image.width, image.height, pad=0.04)]
        cell = max(96, max(image.width, image.height) // 7)
        buckets: dict[tuple[int, int], dict[str, float]] = {}
        for x, y, strength in points:
            key = (int(x // cell), int(y // cell))
            bucket = buckets.setdefault(key, {"score": 0.0, "count": 0.0, "sx": 0.0, "sy": 0.0})
            bucket["score"] += float(strength)
            bucket["count"] += 1.0
            bucket["sx"] += x
            bucket["sy"] += y
        ranked = sorted(buckets.items(), key=lambda item: item[1]["score"], reverse=True)
        boxes: list[tuple[int, int, int, int]] = []
        for _, bucket in ranked:
            if len(boxes) >= limit:
                break
            count = max(1.0, bucket["count"])
            cx = bucket["sx"] / count
            cy = bucket["sy"] / count
            half = cell * self.rng.uniform(0.72, 1.08)
            box = (
                int(max(0, cx - half)),
                int(max(0, cy - half)),
                int(min(image.width - 1, cx + half)),
                int(min(image.height - 1, cy + half)),
            )
            if not self._overlaps_existing(box, boxes):
                boxes.append(box)
        if not boxes:
            boxes.append(self._expanded_bbox(analysis, image.width, image.height, pad=0.04))
        return boxes

    def _overlaps_existing(self, box: tuple[int, int, int, int], boxes: list[tuple[int, int, int, int]]) -> bool:
        x1, y1, x2, y2 = box
        area = max(1, (x2 - x1) * (y2 - y1))
        for ox1, oy1, ox2, oy2 in boxes:
            ix1, iy1 = max(x1, ox1), max(y1, oy1)
            ix2, iy2 = min(x2, ox2), min(y2, oy2)
            if ix2 <= ix1 or iy2 <= iy1:
                continue
            if ((ix2 - ix1) * (iy2 - iy1)) / area > 0.42:
                return True
        return False

    def _paint_cell(self, image, fine: bool) -> int:
        long_side = max(image.width, image.height)
        if fine:
            return max(6, min(18, long_side // 220))
        return max(12, min(34, long_side // 135))

    def _color_stroke_from_pixel(self, image, stage, layer, x, y, brush, opacity, wobble, exact=False) -> BezierStroke:
        r, g, b = image.getpixel((int(x), int(y)))
        spread = 0 if exact else (3 if stage != "polish" else 1)
        color = (
            max(0, min(255, r + self.rng.randint(-spread, spread))),
            max(0, min(255, g + self.rng.randint(-spread, spread))),
            max(0, min(255, b + self.rng.randint(-spread, spread))),
            int(255 * opacity),
        )
        return self._pixel_stroke(stage, layer, x, y, color, brush, opacity, wobble)

    def _pixel_stroke(self, stage, layer, x, y, color, brush, opacity, wobble) -> BezierStroke:
        length = self.rng.uniform(brush * 1.7, brush * 4.8)
        angle = self.rng.choice([0.0, math.pi / 2, -math.pi / 5, math.pi / 5]) + self.rng.uniform(-0.65, 0.65)
        start = (x - math.cos(angle) * length, y - math.sin(angle) * length)
        end = (x + math.cos(angle) * length, y + math.sin(angle) * length)
        duration = self.rng.randint(280, 850) + int(length * 8)
        pause = self.rng.choice([30, 45, 70, 110, 180, 260, 420])
        return self._stroke(stage, layer, start, end, color, self.rng.uniform(brush * 0.55, brush * 1.15), opacity, duration, pause, wobble)

    def _flow_angle(self, x: float, y: float, width: int, height: int) -> float:
        cx = width * 0.5 if width > 1 else x + 100
        cy = height * 0.5 if height > 1 else y + 100
        base = math.atan2(y - cy, x - cx) + math.pi / 2
        return base + self.rng.uniform(-0.45, 0.45)

    def _contour_angle(self, gray, x: float, y: float) -> float:
        xi = max(1, min(gray.width - 2, int(x)))
        yi = max(1, min(gray.height - 2, int(y)))
        gx = gray.getpixel((xi + 1, yi)) - gray.getpixel((xi - 1, yi))
        gy = gray.getpixel((xi, yi + 1)) - gray.getpixel((xi, yi - 1))
        if abs(gx) + abs(gy) < 2:
            return self._flow_angle(x, y, gray.width, gray.height)
        return math.atan2(gy, gx) + math.pi / 2

    def _trace_contour_paths(self, image, analysis: ImageAnalysis) -> list[list[tuple[float, float]]]:
        max_trace_side = 1400
        scale = min(1.0, max_trace_side / max(1, max(image.width, image.height)))
        trace_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        gray = ImageOps.grayscale(image).resize(trace_size, Image.Resampling.LANCZOS)
        edges = gray.filter(ImageFilter.FIND_EDGES)
        arr = np.asarray(edges, dtype=np.uint8)

        x1, y1, x2, y2 = self._expanded_bbox(analysis, image.width, image.height, pad=0.08)
        sx1, sy1 = int(x1 * scale), int(y1 * scale)
        sx2, sy2 = int(x2 * scale), int(y2 * scale)
        mask_area = np.zeros(arr.shape, dtype=bool)
        mask_area[max(0, sy1) : min(arr.shape[0], sy2 + 1), max(0, sx1) : min(arr.shape[1], sx2 + 1)] = True

        active = arr[mask_area]
        if active.size == 0:
            return []
        threshold = max(28, int(np.percentile(active, 88)))
        binary = (arr >= threshold) & mask_area
        return self._edge_components_to_paths(binary, scale)

    def _edge_components_to_paths(self, binary: np.ndarray, scale: float) -> list[list[tuple[float, float]]]:
        h, w = binary.shape
        visited = np.zeros(binary.shape, dtype=bool)
        ys, xs = np.nonzero(binary)
        coords = list(zip(xs.tolist(), ys.tolist()))
        self.rng.shuffle(coords)

        components: list[list[tuple[int, int]]] = []
        for x, y in coords:
            if visited[y, x] or not binary[y, x]:
                continue
            stack = [(x, y)]
            visited[y, x] = True
            comp: list[tuple[int, int]] = []
            while stack and len(comp) < 9000:
                cx, cy = stack.pop()
                comp.append((cx, cy))
                for nx, ny in self._pixel_neighbors(cx, cy, w, h):
                    if not visited[ny, nx] and binary[ny, nx]:
                        visited[ny, nx] = True
                        stack.append((nx, ny))
            if len(comp) >= 24:
                components.append(comp)

        components.sort(key=len, reverse=True)
        paths: list[list[tuple[float, float]]] = []
        for comp in components[: max(18, 34 + self.settings.realism * 3)]:
            ordered = self._order_edge_component(comp)
            if len(ordered) < 18:
                continue
            simplified = self._resample_component_path(ordered, max_points=260)
            inv = 1.0 / max(scale, 1e-6)
            path = [(x * inv, y * inv) for x, y in simplified]
            if self._path_length(path) >= max(28.0, max(w, h) * inv * 0.012):
                paths.append(path)
        paths.sort(key=self._path_length, reverse=True)
        return paths[: max(16, 26 + self.settings.realism * 2)]

    def _pixel_neighbors(self, x: int, y: int, w: int, h: int):
        for ny in range(max(0, y - 1), min(h, y + 2)):
            for nx in range(max(0, x - 1), min(w, x + 2)):
                if nx == x and ny == y:
                    continue
                yield nx, ny

    def _order_edge_component(self, comp: list[tuple[int, int]]) -> list[tuple[float, float]]:
        remaining = set(comp)
        degrees = {}
        for x, y in comp:
            degrees[(x, y)] = sum((nx, ny) in remaining for nx, ny in self._pixel_neighbors_unbounded(x, y))
        endpoints = [pt for pt, degree in degrees.items() if degree <= 1]
        current = min(endpoints or comp, key=lambda pt: (pt[1], pt[0]))
        path = [current]
        remaining.remove(current)
        prev_vec = (1.0, 0.0)

        while remaining:
            candidates = [(nx, ny) for nx, ny in self._pixel_neighbors_unbounded(*current) if (nx, ny) in remaining]
            if not candidates:
                break
            cx, cy = current
            def score(pt):
                vx, vy = pt[0] - cx, pt[1] - cy
                mag = max(1e-6, math.hypot(vx, vy))
                return (vx / mag) * prev_vec[0] + (vy / mag) * prev_vec[1]

            nxt = max(candidates, key=score)
            vx, vy = nxt[0] - cx, nxt[1] - cy
            mag = max(1e-6, math.hypot(vx, vy))
            prev_vec = (vx / mag, vy / mag)
            current = nxt
            remaining.remove(current)
            path.append(current)

        return [(float(x), float(y)) for x, y in path]

    def _pixel_neighbors_unbounded(self, x: int, y: int):
        for ny in (y - 1, y, y + 1):
            for nx in (x - 1, x, x + 1):
                if nx == x and ny == y:
                    continue
                yield nx, ny

    def _resample_component_path(self, points: list[tuple[float, float]], max_points: int) -> list[tuple[float, float]]:
        if len(points) <= max_points:
            return points
        step = max(1, math.ceil(len(points) / max_points))
        sampled = points[::step]
        if sampled[-1] != points[-1]:
            sampled.append(points[-1])
        return sampled

    def _pick(self, points, count):
        points = list(points)
        self.rng.shuffle(points)
        return points[: min(len(points), int(count))]
