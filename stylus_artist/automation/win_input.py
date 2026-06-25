from __future__ import annotations

import ctypes
import math
import time
from ctypes import wintypes

from ..config import CanvasRegion
from ..models.actions import BezierStroke, CanvasAction, DrawingPlan
from ..strokes import ease_in_out


user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]


class WinInputController:
    """Low-level Windows mouse controller.

    This intentionally sends mouse-like input. Real pressure through Windows Ink
    or WinTab requires editor-specific tablet drivers and vendor SDKs; the app
    records pressure in JSON and maps it to brush size/opacity decisions.
    """

    def __init__(self, canvas: CanvasRegion, dry_run: bool = True):
        self.canvas = canvas
        self.dry_run = dry_run or user32 is None

    def replay(self, plan: DrawingPlan, stop_check=lambda: False, pause_check=lambda: False):
        for action in plan.actions:
            if stop_check():
                break
            while pause_check():
                time.sleep(0.05)
            if isinstance(action, BezierStroke):
                self.stroke(action, plan.width, plan.height)
            elif isinstance(action, CanvasAction):
                self.canvas_action(action)

    def stroke(self, stroke: BezierStroke, width: int, height: int):
        if not stroke.points:
            return
        points = [self._map_point(p, width, height) for p in stroke.points]
        self._move_smooth(points[0], 260)
        self._mouse_down()
        start = time.perf_counter()
        total = max(0.01, stroke.duration_ms / 1000)
        for i, point in enumerate(points[1:], 1):
            t = ease_in_out(i / max(1, len(points) - 1))
            target_time = start + total * t
            self._move_smooth(point, max(14, int(total * 1000 / max(1, len(points)))))
            delay = target_time - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
        self._mouse_up()
        if stroke.pause_after_ms:
            time.sleep(stroke.pause_after_ms / 1000)

    def canvas_action(self, action: CanvasAction):
        # External editor shortcuts are intentionally conservative. The visual
        # preview performs full rotation/zoom; external mode keeps mouse replay
        # stable unless users customize shortcuts later.
        time.sleep((action.duration_ms + action.pause_after_ms) / 1000)

    def _map_point(self, point, width, height):
        x, y = point
        return (
            self.canvas.x + int((x / max(1, width)) * self.canvas.width),
            self.canvas.y + int((y / max(1, height)) * self.canvas.height),
        )

    def _move_smooth(self, point, duration_ms: int):
        if self.dry_run:
            time.sleep(duration_ms / 1000)
            return
        sx, sy = self._cursor()
        ex, ey = point
        steps = max(8, min(140, int(math.dist((sx, sy), (ex, ey)) / 4)))
        for i in range(1, steps + 1):
            t = ease_in_out(i / steps)
            x = int(sx + (ex - sx) * t)
            y = int(sy + (ey - sy) * t)
            self._send_move(x, y)
            time.sleep(max(0.001, duration_ms / 1000 / steps))

    def _cursor(self):
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def _send_move(self, x, y):
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        ax = int(x * 65535 / max(1, sw - 1))
        ay = int(y * 65535 / max(1, sh - 1))
        self._send_mouse(ax, ay, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE)

    def _mouse_down(self):
        if not self.dry_run:
            self._send_mouse(0, 0, MOUSEEVENTF_LEFTDOWN)

    def _mouse_up(self):
        if not self.dry_run:
            self._send_mouse(0, 0, MOUSEEVENTF_LEFTUP)

    def _send_mouse(self, x, y, flags):
        inp = INPUT(type=INPUT_MOUSE, union=INPUT_UNION(mi=MOUSEINPUT(x, y, 0, flags, 0, None)))
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
