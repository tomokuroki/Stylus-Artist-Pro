from __future__ import annotations

import random
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps, ImageTk

from ..automation.win_input import WinInputController
from ..config import EDITOR_PROFILES, EXPORT_DIR, INPUT_DIR, PLANS_DIR, SimulationSettings
from ..planner import DrawingPlanner
from ..recorder import load_plan, save_plan
from ..renderer import PlanRenderer
from ..simulator import ExternalReplay, PreviewSimulator
from ..vision.analysis import load_image


class StylusArtistTk:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Stylus Artist Pro")
        self.root.geometry("1320x920")
        self.root.minsize(1060, 760)

        INPUT_DIR.mkdir(exist_ok=True)
        PLANS_DIR.mkdir(exist_ok=True)
        EXPORT_DIR.mkdir(exist_ok=True)

        self.source_path: Path | None = None
        self.source_image = None
        self.plan = None
        self.renderer: PlanRenderer | None = None
        self.external: ExternalReplay | None = None
        self.preview_running = False
        self.preview_paused = False
        self.building_plan = False
        self.photo = None

        self.realism = tk.IntVar(value=8)
        self.speed = tk.IntVar(value=3)
        self.rotation_frequency = tk.IntVar(value=5)
        self.sketch_passes = tk.IntVar(value=3)
        self.seed = tk.IntVar(value=random.randint(1000, 999999))
        self.fps = tk.IntVar(value=30)
        self.seconds = tk.IntVar(value=45)
        self.editor = tk.StringVar(value="Preview only")
        self.dry_run = tk.BooleanVar(value=True)
        self.canvas_x = tk.IntVar(value=260)
        self.canvas_y = tk.IntVar(value=120)
        self.canvas_w = tk.IntVar(value=900)
        self.canvas_h = tk.IntVar(value=900)
        self.status = tk.StringVar(value="Загрузи PNG/JPG или положи файл в input_images.")

        self._build()
        self._load_latest_silent()

    def _build(self):
        self.root.configure(bg="#eceae4")
        top = ttk.Frame(self.root, padding=(12, 10))
        top.pack(side=tk.TOP, fill=tk.X)

        buttons = [
            ("Загрузить", self.load_image_dialog),
            ("Из input_images", self.load_latest_from_folder),
            ("Построить план", self.build_plan),
            ("Старт preview", self.start_preview),
            ("Пауза", self.pause),
            ("Стоп", self.stop),
            ("JSON", self.save_json),
            ("Загрузить JSON", self.load_json),
            ("Экспорт кадров", self.export_frames),
            ("Внешний редактор", self.start_external),
        ]
        for text, cmd in buttons:
            ttk.Button(top, text=text, command=cmd).pack(side=tk.LEFT, padx=(0, 7))

        body = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        body.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(left, bg="#d8d3c8", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        ttk.Label(left, textvariable=self.status, anchor="w").pack(fill=tk.X, pady=(8, 0))

        right = ttk.Frame(body, width=360)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))
        right.pack_propagate(False)

        self._settings(right)
        self.log = tk.Text(right, height=18, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self._log("Архитектура: analysis -> planner -> renderer -> recorder -> win_input.")

    def _settings(self, parent):
        ttk.Label(parent, text="Настройки реалистичности").pack(anchor="w")
        self._slider(parent, "Реализм", self.realism, 1, 10)
        self._slider(parent, "Скорость", self.speed, 1, 10)
        self._slider(parent, "Повороты холста", self.rotation_frequency, 1, 10)
        self._slider(parent, "Кол-во набросков", self.sketch_passes, 1, 7)
        self._slider(parent, "FPS экспорта", self.fps, 12, 60)
        self._slider(parent, "Длина, сек", self.seconds, 8, 120)

        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(row, text="Seed").pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.seed, width=10).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(row, text="Новый", command=lambda: self.seed.set(random.randint(1000, 999999))).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(parent, text="Редактор").pack(anchor="w", pady=(12, 0))
        ttk.Combobox(parent, textvariable=self.editor, values=list(EDITOR_PROFILES), state="readonly").pack(fill=tk.X)
        ttk.Checkbutton(parent, text="Dry-run: не двигать реальную мышь", variable=self.dry_run).pack(anchor="w", pady=(8, 0))

        ttk.Label(parent, text="Область холста внешнего редактора").pack(anchor="w", pady=(12, 0))
        grid = ttk.Frame(parent)
        grid.pack(fill=tk.X)
        for i, (label, var) in enumerate((("X", self.canvas_x), ("Y", self.canvas_y), ("W", self.canvas_w), ("H", self.canvas_h))):
            ttk.Label(grid, text=label).grid(row=0, column=i * 2, sticky="w")
            ttk.Entry(grid, textvariable=var, width=6).grid(row=0, column=i * 2 + 1, padx=(3, 8))

    def _slider(self, parent, label, var, lo, hi):
        box = ttk.Frame(parent)
        box.pack(fill=tk.X, pady=(8, 0))
        row = ttk.Frame(box)
        row.pack(fill=tk.X)
        ttk.Label(row, text=label).pack(side=tk.LEFT)
        ttk.Label(row, textvariable=var, width=4, anchor="e").pack(side=tk.RIGHT)
        ttk.Scale(box, from_=lo, to=hi, variable=var, orient=tk.HORIZONTAL).pack(fill=tk.X)

    def settings(self) -> SimulationSettings:
        s = SimulationSettings(
            realism=int(self.realism.get()),
            speed=int(self.speed.get()),
            rotation_frequency=int(self.rotation_frequency.get()),
            sketch_passes=int(self.sketch_passes.get()),
            seed=int(self.seed.get()),
            output_fps=int(self.fps.get()),
            output_seconds=int(self.seconds.get()),
            editor=self.editor.get(),
            dry_run=self.dry_run.get(),
        )
        s.canvas.x = int(self.canvas_x.get())
        s.canvas.y = int(self.canvas_y.get())
        s.canvas.width = int(self.canvas_w.get())
        s.canvas.height = int(self.canvas_h.get())
        return s

    def load_image_dialog(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp")])
        if path:
            self._load_image(Path(path))

    def load_latest_from_folder(self):
        if not self._load_latest_silent():
            messagebox.showinfo("Папка пустая", f"Положи PNG/JPG в {INPUT_DIR}")

    def _load_latest_silent(self) -> bool:
        files = [p for p in INPUT_DIR.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}]
        if not files:
            self._show_blank()
            return False
        self._load_image(max(files, key=lambda p: p.stat().st_mtime))
        return True

    def _load_image(self, path: Path):
        self.source_path = path
        self.source_image = load_image(path)
        self.plan = None
        self.renderer = None
        self.status.set(f"Загружено: {path.name}. Нажми 'Построить план'.")
        self._log(f"image: {path.name}, size={self.source_image.size}")
        self._show_image(self.source_image)

    def build_plan(self):
        if self.building_plan:
            self.status.set("План уже строится в фоне...")
            return
        if self.source_image is None:
            self.load_image_dialog()
            if self.source_image is None:
                return
        self.building_plan = True
        self.status.set("Строю план в фоне: окно не зависло, можно ждать спокойно.")
        image = self.source_image.copy()
        source = self.source_path or "unknown"
        settings = self.settings()

        def worker():
            try:
                planner = DrawingPlanner(settings)
                plan = planner.build(image, source)
                self.root.after(0, lambda: self._finish_build_plan(plan, None))
            except Exception as exc:
                self.root.after(0, lambda: self._finish_build_plan(None, exc))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_build_plan(self, plan, error):
        self.building_plan = False
        if error is not None:
            self.status.set(f"Ошибка построения плана: {error}")
            self._log(f"plan error: {error}")
            return
        self.plan = plan
        self.renderer = PlanRenderer(self.plan)
        self._log(f"plan: {len(self.plan.actions)} actions, backend={self.plan.analysis.get('backend')}")
        self._log(f"stages: {self.plan.analysis.get('counts')}")
        self.status.set(f"План готов: {len(self.plan.actions)} действий. Можно запускать preview или экспорт.")
        self._show_image(self.renderer.image(False, False, max_side=1600))

    def start_preview(self):
        if self.plan is None:
            if self.building_plan:
                self.status.set("Дождись готового плана, он сейчас строится в фоне.")
                return
            self.build_plan()
            if self.plan is None:
                return
        self.renderer = PlanRenderer(self.plan)
        self.preview_running = True
        self.preview_paused = False
        self._preview_tick()

    def _preview_tick(self):
        if not self.preview_running or self.renderer is None:
            return
        if self.preview_paused:
            self.root.after(100, self._preview_tick)
            return
        step = max(80, int(self.speed.get()) * 320)
        done = self.renderer.step(step)
        self._show_image(self.renderer.image(True, True, max_side=1600))
        self.status.set(f"Preview {int(self.renderer.progress() * 100)}% | действие {self.renderer.index}/{len(self.plan.actions)}")
        if done:
            self.preview_running = False
            self.status.set("Preview завершен.")
            return
        self.root.after(max(20, int(95 / max(1, self.speed.get()))), self._preview_tick)

    def pause(self):
        self.preview_paused = not self.preview_paused
        if self.external:
            self.external.pause()
        self.status.set("Пауза." if self.preview_paused else "Продолжаю.")

    def stop(self):
        self.preview_running = False
        if self.external:
            self.external.stop()
        self.status.set("Остановлено.")

    def start_external(self):
        if self.plan is None:
            self.build_plan()
            if self.plan is None:
                return
        if not self.dry_run.get():
            ok = messagebox.askyesno(
                "Реальное управление мышью",
                "Программа начнет двигать мышью в активном Windows-окне. Открой редактор, выбери кисть и подготовь холст. Продолжить?",
            )
            if not ok:
                return
        controller = WinInputController(self.settings().canvas, dry_run=self.dry_run.get())
        self.external = ExternalReplay(self.plan, controller)
        self.external.start()
        self._log(f"external replay started: editor={self.editor.get()}, dry_run={self.dry_run.get()}")

    def save_json(self):
        if self.plan is None:
            self.build_plan()
            if self.plan is None:
                return
        default = PLANS_DIR / f"plan_{self.seed.get()}.json"
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile=default.name, initialdir=str(PLANS_DIR))
        if path:
            save_plan(self.plan, path)
            self._log(f"json saved: {path}")

    def load_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON plan", "*.json")], initialdir=str(PLANS_DIR))
        if not path:
            return
        self.plan = load_plan(path)
        self.renderer = PlanRenderer(self.plan)
        self.status.set(f"Загружен план: {Path(path).name}")
        self._log(f"json loaded: {path}, actions={len(self.plan.actions)}")
        self._show_image(self.renderer.image(False, False))

    def export_frames(self):
        if self.plan is None:
            self.build_plan()
            if self.plan is None:
                return
        folder = filedialog.askdirectory(initialdir=str(EXPORT_DIR))
        if not folder:
            return
        self.status.set("Экспортирую кадры...")

        def worker():
            sim = PreviewSimulator(self.plan)
            count = sim.export_frames(Path(folder) / "frames", int(self.fps.get()), int(self.seconds.get()))
            self.root.after(0, lambda: self.status.set(f"Экспорт готов: {count} PNG кадров."))
            self.root.after(0, lambda: self._log(f"export: {count} frames -> {folder}"))

        threading.Thread(target=worker, daemon=True).start()

    def _show_blank(self):
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (900, 900), (248, 246, 240))
        d = ImageDraw.Draw(img)
        d.rectangle((50, 50, 850, 850), outline=(196, 190, 178), width=3)
        d.text((80, 88), "Stylus Artist Pro: загрузите изображение", fill=(65, 65, 65))
        self._show_image(img)

    def _show_image(self, image):
        cw = max(200, self.canvas.winfo_width())
        ch = max(200, self.canvas.winfo_height())
        preview = ImageOps.contain(image.convert("RGB"), (cw, ch), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(preview)
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self.photo, anchor=tk.CENTER)

    def _log(self, text: str):
        ts = time.strftime("%H:%M:%S")
        self.log.insert(tk.END, f"[{ts}] {text}\n")
        self.log.see(tk.END)


def run():
    root = tk.Tk()
    style = ttk.Style()
    if "clam" in style.theme_names():
        style.theme_use("clam")
    StylusArtistTk(root)
    root.mainloop()
