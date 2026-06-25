from __future__ import annotations

import threading
import time
from pathlib import Path

from .automation.win_input import WinInputController
from .models.actions import DrawingPlan
from .renderer import PlanRenderer


class PlaybackState:
    def __init__(self):
        self.running = False
        self.paused = False
        self.stop_requested = False


class PreviewSimulator:
    def __init__(self, plan: DrawingPlan):
        self.renderer = PlanRenderer(plan)
        self.state = PlaybackState()

    def reset(self):
        self.renderer.reset()
        self.state = PlaybackState()

    def export_frames(self, folder: str | Path, fps: int, seconds: int) -> int:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        self.renderer.reset()
        total = max(1, fps * seconds)
        actions_per_frame = max(1, self.renderer.total_work_units() // total)
        saved = 0
        while self.renderer.index < len(self.renderer.plan.actions):
            self.renderer.step(actions_per_frame)
            self.renderer.image(show_cursor=True, rotate=True).save(folder / f"frame_{saved:05d}.png")
            saved += 1
        return saved


class ExternalReplay:
    def __init__(self, plan: DrawingPlan, controller: WinInputController):
        self.plan = plan
        self.controller = controller
        self.state = PlaybackState()
        self.thread: threading.Thread | None = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.state.running = True
        self.state.stop_requested = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            self.controller.replay(
                self.plan,
                stop_check=lambda: self.state.stop_requested,
                pause_check=lambda: self.state.paused,
            )
        finally:
            self.state.running = False

    def pause(self):
        self.state.paused = not self.state.paused

    def stop(self):
        self.state.stop_requested = True
        time.sleep(0.05)
