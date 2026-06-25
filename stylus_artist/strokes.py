from __future__ import annotations

import math
import random


def bezier_curve(points: list[tuple[float, float]], samples: int = 24) -> list[tuple[float, float]]:
    if len(points) < 2:
        return points
    result = []
    for i in range(samples):
        t = i / max(1, samples - 1)
        result.append(_de_casteljau(points, t))
    return result


def _de_casteljau(points: list[tuple[float, float]], t: float) -> tuple[float, float]:
    pts = [(float(x), float(y)) for x, y in points]
    while len(pts) > 1:
        pts = [
            (pts[i][0] * (1 - t) + pts[i + 1][0] * t, pts[i][1] * (1 - t) + pts[i + 1][1] * t)
            for i in range(len(pts) - 1)
        ]
    return pts[0]


def humanized_path(
    start: tuple[float, float],
    end: tuple[float, float],
    rng: random.Random,
    wobble: float,
    samples: int,
) -> list[tuple[float, float]]:
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    dist = max(1.0, math.hypot(dx, dy))
    nx, ny = -dy / dist, dx / dist
    c1 = (
        sx + dx * rng.uniform(0.20, 0.42) + nx * rng.uniform(-wobble, wobble),
        sy + dy * rng.uniform(0.20, 0.42) + ny * rng.uniform(-wobble, wobble),
    )
    c2 = (
        sx + dx * rng.uniform(0.58, 0.82) + nx * rng.uniform(-wobble, wobble),
        sy + dy * rng.uniform(0.58, 0.82) + ny * rng.uniform(-wobble, wobble),
    )
    path = bezier_curve([start, c1, c2, end], samples)
    return add_micro_jitter(path, rng, wobble * 0.22)


def add_micro_jitter(points: list[tuple[float, float]], rng: random.Random, amount: float) -> list[tuple[float, float]]:
    out = []
    for i, (x, y) in enumerate(points):
        if i in (0, len(points) - 1):
            out.append((x, y))
        else:
            out.append((x + rng.gauss(0, amount), y + rng.gauss(0, amount)))
    return out


def pressure_curve(samples: int, rng: random.Random, base: float = 0.75) -> list[float]:
    values = []
    for i in range(samples):
        t = i / max(1, samples - 1)
        ease = math.sin(math.pi * t)
        values.append(max(0.08, min(1.0, base * (0.35 + 0.65 * ease) + rng.gauss(0, 0.035))))
    return values


def ease_in_out(t: float) -> float:
    return t * t * (3 - 2 * t)
