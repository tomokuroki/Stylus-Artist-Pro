from __future__ import annotations

from collections import defaultdict

from PIL import Image, ImageDraw, ImageFilter

from .models.actions import BezierStroke, CanvasAction, DrawingPlan


PAPER = (248, 246, 240, 255)
LAYER_ALPHA = {
    "guides": 0.55,
    "sketch": 0.70,
    "construction": 0.50,
    "lineart": 0.95,
    "base_color": 0.96,
    "details": 1.0,
    "shadows": 0.86,
    "highlights": 0.92,
    "polish": 1.0,
    "region_finish": 1.0,
    "pixel_finish": 1.0,
}

LAYER_ORDER = [
    "guides",
    "sketch",
    "construction",
    "base_color",
    "shadows",
    "details",
    "lineart",
    "highlights",
    "polish",
    "region_finish",
    "pixel_finish",
]
OPAQUE_DIGITAL_LAYERS = {"base_color", "details", "polish", "region_finish", "pixel_finish"}


class PlanRenderer:
    def __init__(self, plan: DrawingPlan):
        self.plan = plan
        self.layers: dict[str, Image.Image] = {}
        self.index = 0
        self.cursor: tuple[float, float] | None = None
        self.rotation = 0.0
        self.zoom = 1.0
        self.focus_center: tuple[float, float] | None = None
        self.stage_counts = defaultdict(int)
        self.active_stroke: BezierStroke | None = None
        self.active_segment = 1
        self.work_done = 0
        self._total_work = self._calculate_total_work()

    def reset(self):
        self.layers.clear()
        self.index = 0
        self.cursor = None
        self.rotation = 0.0
        self.zoom = 1.0
        self.focus_center = None
        self.stage_counts.clear()
        self.active_stroke = None
        self.active_segment = 1
        self.work_done = 0

    def step(self, count: int = 1) -> bool:
        for _ in range(count):
            if self.active_stroke is not None:
                self._draw_stroke_segment(self.active_stroke, self.active_segment)
                self.cursor = self.active_stroke.points[self.active_segment]
                self.active_segment += 1
                self.work_done += 1
                if self.active_segment >= len(self.active_stroke.points):
                    stroke = self.active_stroke
                    self.rotation = stroke.canvas_rotation
                    self.zoom = stroke.canvas_zoom
                    self.stage_counts[stroke.stage] += 1
                    self.active_stroke = None
                    self.active_segment = 1
                    self.index += 1
                continue
            if self.index >= len(self.plan.actions):
                return True
            action = self.plan.actions[self.index]
            if isinstance(action, BezierStroke):
                if len(action.points) < 2:
                    self.index += 1
                    continue
                self.active_stroke = action
                self.active_segment = 1
                self.cursor = action.points[0]
            elif isinstance(action, CanvasAction):
                self.index += 1
                self.work_done += 1
                if action.action == "rotate":
                    self.rotation = action.value
                elif action.action == "zoom":
                    self.zoom = action.value
                elif action.action == "focus_x":
                    y = self.focus_center[1] if self.focus_center else self.plan.height / 2
                    self.focus_center = (action.value, y)
                elif action.action == "focus_y":
                    x = self.focus_center[0] if self.focus_center else self.plan.width / 2
                    self.focus_center = (x, action.value)
        return self.index >= len(self.plan.actions)

    def _layer(self, name: str) -> Image.Image:
        if name not in self.layers:
            self.layers[name] = Image.new("RGBA", (self.plan.width, self.plan.height), (0, 0, 0, 0))
        return self.layers[name]

    def _draw_stroke(self, stroke: BezierStroke):
        for i in range(1, len(stroke.points)):
            self._draw_stroke_segment(stroke, i)

    def _draw_stroke_segment(self, stroke: BezierStroke, i: int):
        layer = self._layer(stroke.layer)
        draw = ImageDraw.Draw(layer, "RGBA")
        pts = stroke.points
        if i <= 0 or i >= len(pts):
            return
        p = stroke.pressure[min(i, len(stroke.pressure) - 1)]
        if stroke.layer in OPAQUE_DIGITAL_LAYERS:
            alpha = int(stroke.color[3] * LAYER_ALPHA.get(stroke.layer, 1.0))
        else:
            alpha = int(stroke.color[3] * p * LAYER_ALPHA.get(stroke.layer, 1.0))
        color = (*stroke.color[:3], max(1, min(255, alpha)))
        width = max(1, int(stroke.brush_size * (0.45 + 0.75 * p)))
        draw.line([pts[i - 1], pts[i]], fill=color, width=width, joint="curve")
        if stroke.layer in OPAQUE_DIGITAL_LAYERS and width > 2:
            radius = width / 2
            for x, y in (pts[i - 1], pts[i]):
                draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
        if stroke.layer in {"shadows", "highlights"} and stroke.brush_size > 8:
            self.layers[stroke.layer] = layer.filter(ImageFilter.GaussianBlur(0.25))

    def image(self, show_cursor: bool = True, rotate: bool = True, max_side: int | None = None) -> Image.Image:
        render_scale = 1.0
        out_w, out_h = self.plan.width, self.plan.height
        if max_side and max(self.plan.width, self.plan.height) > max_side:
            render_scale = max_side / max(self.plan.width, self.plan.height)
            out_w = max(1, int(self.plan.width * render_scale))
            out_h = max(1, int(self.plan.height * render_scale))

        composed = Image.new("RGBA", (out_w, out_h), PAPER)
        for name in LAYER_ORDER:
            if name in self.layers:
                layer = self._visible_layer(name)
                if render_scale != 1.0:
                    layer = layer.resize((out_w, out_h), Image.Resampling.BILINEAR)
                composed = Image.alpha_composite(composed, layer)

        if show_cursor and self.cursor:
            overlay = Image.new("RGBA", composed.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(overlay, "RGBA")
            x, y = self.cursor[0] * render_scale, self.cursor[1] * render_scale
            d.ellipse((x - 6, y - 6, x + 6, y + 6), outline=(20, 20, 20, 200), width=2)
            d.line((x + 8, y + 9, x + 36, y + 36), fill=(20, 20, 20, 210), width=4)
            d.line((x + 11, y + 8, x + 39, y + 33), fill=(235, 235, 235, 210), width=2)
            composed = Image.alpha_composite(composed, overlay)

        if rotate and self.zoom > 1.03:
            composed = self._zoomed_view(composed, render_scale)

        if rotate:
            angle = max(-18.0, min(18.0, self.rotation))
            composed = composed.rotate(angle, resample=Image.Resampling.BICUBIC, fillcolor=(226, 222, 214, 255))
        return composed.convert("RGB")

    def _zoomed_view(self, image: Image.Image, render_scale: float) -> Image.Image:
        zoom = max(1.0, min(3.5, self.zoom))
        width, height = image.size
        view_w = max(64, int(width / zoom))
        view_h = max(64, int(height / zoom))
        if self.cursor:
            cx, cy = self.cursor[0] * render_scale, self.cursor[1] * render_scale
        elif self.focus_center:
            cx, cy = self.focus_center[0] * render_scale, self.focus_center[1] * render_scale
        else:
            cx, cy = width / 2, height / 2
        x1 = int(max(0, min(width - view_w, cx - view_w / 2)))
        y1 = int(max(0, min(height - view_h, cy - view_h / 2)))
        crop = image.crop((x1, y1, x1 + view_w, y1 + view_h))
        return crop.resize((width, height), Image.Resampling.LANCZOS)

    def progress(self) -> float:
        return self.work_done / max(1, self.total_work_units())

    def total_work_units(self) -> int:
        return self._total_work

    def _calculate_total_work(self) -> int:
        total = 0
        for action in self.plan.actions:
            if isinstance(action, BezierStroke):
                total += max(1, len(action.points) - 1)
            else:
                total += 1
        return total

    def _visible_layer(self, name: str) -> Image.Image:
        layer = self.layers[name]
        fade = 1.0
        if name in {"guides", "construction"} and self.stage_counts["line_refine"] > 20:
            fade = 0.16
        elif name == "sketch" and self.stage_counts["color_blocking"] > 10:
            fade = 0.24
        if fade >= 0.99:
            return layer
        faded = layer.copy()
        alpha = faded.getchannel("A").point(lambda a: int(a * fade))
        faded.putalpha(alpha)
        return faded
