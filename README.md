# Stylus Artist Pro

## 中文说明（主要文档）

### 概述

**Stylus Artist Pro** 是一款基于 Python 的 Windows 桌面应用程序，用于模拟数字艺术家的真实绘画流程。

程序不会将原始图片直接粘贴到画布上，而是会：

* 分析参考图像
* 识别构图与视觉重心
* 提取轮廓与颜色关系
* 生成数千条仿真人 Bézier 笔触
* 创建完整绘画计划
* 保存为 JSON
* 在内部预览窗口重放绘画过程
* 或通过鼠标自动化在外部绘图软件中执行

最终效果类似于真实画师从草稿到成稿的完整绘制过程。

---

## 核心特性

### 智能图像分析

分析内容包括：

* 边缘与轮廓
* 构图结构
* 视觉焦点
* 明暗关系
* 阴影与高光
* 主色板
* 细节密度

支持：

* OpenCV（可选）
* Pillow
* NumPy

即使没有 OpenCV 也能正常运行。

---

### 仿真人绘画阶段

Stylus Artist Pro 将绘画拆分为多个阶段：

1. Observe（观察）
2. Composition（构图）
3. Rough Sketch（草稿）
4. Construction（结构搭建）
5. Line Refine（线稿优化）
6. Digital Color Blocking（铺色）
7. Details（细节刻画）
8. Shadows（阴影）
9. Highlights（高光）
10. Polish（润色）
11. Pixel Finish（像素级修正）

每个阶段都会生成独立动作并记录到 JSON。

---

### 真实笔触模拟

系统支持：

* Bézier 曲线笔画
* 手部抖动模拟
* 压感曲线
* 加速度与减速度
* 停顿与观察时间
* 画布旋转
* 扫描线式数字绘制

从而使整个绘画过程更加自然。

---

### JSON Replay

所有绘画动作均可保存：

```json
{
  "stage": "rough_sketch",
  "points": [...],
  "pressure": [...],
  "duration": 1.42
}
```

同一个 Seed 可获得完全可重复的绘制过程。

---

### Preview Renderer

内置预览系统支持：

* 分层渲染
* 实时播放
* Stylus 光标显示
* 画布旋转动画
* PNG 帧序列导出

适用于：

* TikTok
* YouTube Shorts
* Reels
* 绘画过程视频制作

---

### 外部绘图软件支持

支持配置：

* Adobe Photoshop
* Krita
* Paint Tool SAI
* Clip Studio Paint
* Preview Only

工作方式：

1. 打开绘图软件
2. 创建空白画布
3. 设置画布区域 X/Y/W/H
4. 关闭 Dry-Run
5. 启动 External Editor 模式

程序将通过 Windows SendInput 控制鼠标进行绘制。

---

## 项目结构

```text
New project 2/
│
├── artist_stylus.py
├── run_stylus_painter.bat
│
├── input_images/
├── plans/
├── exports/
│
└── stylus_artist/
    ├── app.py
    ├── config.py
    ├── planner.py
    ├── renderer.py
    ├── recorder.py
    ├── simulator.py
    ├── strokes.py
    │
    ├── models/
    │   └── actions.py
    │
    ├── vision/
    │   └── analysis.py
    │
    ├── automation/
    │   └── win_input.py
    │
    └── ui/
        ├── tk_app.py
        └── qt_app.py
```

---

## 安装

### Python

推荐：

```bash
Python 3.10+
```

---

### 安装依赖

```bash
pip install pillow numpy
```

可选：

```bash
pip install opencv-python
```

---

## 启动

双击：

```text
run_stylus_painter.bat
```

或者：

```bash
python -m stylus_artist.app
```

---

## 使用方法

### 1. 导入图片

将 PNG/JPG 放入：

```text
input_images
```

或点击：

```text
Load Image
```

---

### 2. 调整参数

可设置：

* Realism
* Speed
* Canvas Rotation Frequency
* Sketch Passes
* Seed

---

### 3. 生成绘画计划

点击：

```text
Build Plan
```

---

### 4. 预览绘画过程

点击：

```text
Start Preview
```

---

### 5. 导出 JSON

点击：

```text
Save JSON
```

---

### 6. 导出视频帧

点击：

```text
Export Frames
```

PNG 序列将保存到：

```text
exports/
```

---

## 推荐设置

适用于 TikTok / Shorts：

```text
Speed: 2~4
Realism: High
Rotation: Medium
Sketch Passes: 3~5
```

这样会获得更自然、更像真人绘画的视频效果。

---

## 压感说明

程序内部记录：

* Pressure
* Opacity
* Stroke Size

但外部编辑器模式目前通过：

```text
Win32 SendInput
```

模拟鼠标。

真正的数位板压感支持取决于：

* Windows Ink
* WinTab
* 驱动程序
* 绘图软件 API

未来版本可扩展支持。

---

## AI 与计算机视觉扩展

当前项目无需安装：

* PyQt6
* Torch
* ONNX Runtime
* MediaPipe
* SAM2
* Grounding DINO

未来可直接接入：

```text
vision/analysis.py
```

无需修改：

* planner
* renderer
* simulator

即可获得更高级视觉分析能力。

---

## 许可证

仅供学习、研究与创意开发使用。

Stylus Artist Pro ©
