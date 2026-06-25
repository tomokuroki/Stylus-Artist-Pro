from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps


try:
    import cv2  # type: ignore
except Exception:
    cv2 = None


@dataclass
class ImageAnalysis:
    width: int
    height: int
    composition: dict
    palette: list[tuple[int, int, int]]
    edge_points: list[tuple[int, int, int]]
    shadow_points: list[tuple[int, int, int]]
    highlight_points: list[tuple[int, int, int]]
    detail_points: list[tuple[int, int, int]]
    saliency_points: list[tuple[int, int, int]]

    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "composition": self.composition,
            "palette": self.palette,
            "counts": {
                "edges": len(self.edge_points),
                "shadows": len(self.shadow_points),
                "highlights": len(self.highlight_points),
                "details": len(self.detail_points),
                "saliency": len(self.saliency_points),
            },
            "backend": "OpenCV" if cv2 else "Pillow/NumPy",
        }


def load_image(path: str | Path, target_side: int = 4096) -> Image.Image:
    image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    longest = max(image.size)
    if longest == target_side:
        return image
    scale = target_side / max(1, longest)
    size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    return image.resize(size, Image.Resampling.LANCZOS)


def analyze_image(image: Image.Image, realism: int = 8) -> ImageAnalysis:
    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    h, w = rgb.shape[:2]
    gray = np.asarray(ImageOps.grayscale(image), dtype=np.uint8)

    if cv2:
        edges = cv2.Canny(gray, 45, 140)
        blur = cv2.GaussianBlur(gray, (0, 0), 5)
        detail_map = cv2.absdiff(gray, blur)
    else:
        edge_img = ImageOps.grayscale(image).filter(ImageFilter.FIND_EDGES)
        edges = np.asarray(edge_img, dtype=np.uint8)
        blur = np.asarray(ImageOps.grayscale(image).filter(ImageFilter.GaussianBlur(5)), dtype=np.uint8)
        detail_map = np.abs(gray.astype(np.int16) - blur.astype(np.int16)).astype(np.uint8)

    luminance = gray.astype(np.float32)
    shadows = np.clip(120 - luminance, 0, 120).astype(np.uint8)
    highlights = np.clip(luminance - 168, 0, 87).astype(np.uint8)
    saliency = np.maximum(edges, detail_map)

    edge_points = _sample_map(edges, 24, 6, realism)
    shadow_points = _sample_map(shadows, 18, 10, realism)
    highlight_points = _sample_map(highlights, 18, 10, realism)
    detail_points = _sample_map(detail_map, 14, 7, realism)
    saliency_points = _sample_map(saliency, 20, 8, realism)
    palette = _palette(rgb, k=min(12, 5 + realism))
    composition = _composition(gray, saliency)

    return ImageAnalysis(
        width=w,
        height=h,
        composition=composition,
        palette=palette,
        edge_points=edge_points,
        shadow_points=shadow_points,
        highlight_points=highlight_points,
        detail_points=detail_points,
        saliency_points=saliency_points,
    )


def _sample_map(values: np.ndarray, threshold: int, stride: int, realism: int) -> list[tuple[int, int, int]]:
    points: list[tuple[int, int, int]] = []
    h, w = values.shape[:2]
    stride = max(2, stride - realism // 3)
    for y in range(stride, h - stride, stride):
        row = values[y]
        for x in range(stride, w - stride, stride):
            v = int(row[x])
            if v > threshold:
                points.append((x, y, v))
    points.sort(key=lambda p: p[2], reverse=True)
    return points[: max(100, 6500 + realism * 900)]


def _palette(rgb: np.ndarray, k: int) -> list[tuple[int, int, int]]:
    pixels = rgb.reshape(-1, 3)
    if len(pixels) > 18000:
        idx = np.linspace(0, len(pixels) - 1, 18000).astype(int)
        pixels = pixels[idx]
    quantized = (pixels // 24) * 24
    colors, counts = np.unique(quantized, axis=0, return_counts=True)
    order = np.argsort(counts)[::-1][:k]
    return [tuple(int(c) for c in colors[i]) for i in order]


def _composition(gray: np.ndarray, saliency: np.ndarray) -> dict:
    h, w = gray.shape
    ys, xs = np.nonzero(saliency > max(24, int(np.percentile(saliency, 82))))
    if len(xs) == 0:
        return {"center": (w / 2, h / 2), "bbox": (0, 0, w, h), "rule_of_thirds": []}
    weights = saliency[ys, xs].astype(np.float64) + 1.0
    cx = float(np.average(xs, weights=weights))
    cy = float(np.average(ys, weights=weights))
    bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    thirds = [(w / 3, h / 3), (2 * w / 3, h / 3), (w / 3, 2 * h / 3), (2 * w / 3, 2 * h / 3)]
    return {"center": (cx, cy), "bbox": bbox, "rule_of_thirds": thirds}
