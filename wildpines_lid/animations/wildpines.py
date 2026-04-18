"""Wild Pines AI animation, matching g-helper's STRIX Text() layout.

Canvas: 68 wide x 39 tall, delta_x=5, delta_y=24. Valid projection region is
x∈[0,62], y∈[24,38] — a 63x15 band at the bottom of the canvas.

Stages (~8s loop):
  0  dark             300 ms
  1  slash wake       600 ms  — horizontal wipe left->right
  2  text fade in     1200 ms — 'WILD PINES AI' materializes
  3  breathe          4000 ms — gentle pulse
  4  fade out         800 ms
  5  pause            600 ms
"""

from __future__ import annotations

import math
from collections.abc import Iterator

from PIL import Image, ImageDraw, ImageFont

from ..canvas import DiagonalCanvas

FPS = 30
FRAME_MS = 1000 // FPS

CANVAS_W = 68
CANVAS_H = 39
DELTA_X = 5
DELTA_Y = 24

# Usable band (empirically: the 63x15 region at the bottom of the canvas
# projects to valid LEDs)
BAND_Y_MIN = 24
BAND_Y_MAX = 38
BAND_HEIGHT = BAND_Y_MAX - BAND_Y_MIN + 1
BAND_X_MIN = 0
BAND_X_MAX = 62
BAND_WIDTH = BAND_X_MAX - BAND_X_MIN + 1

LINES = ("WILD PINES", "AI")
FONT_SIZE = 9
LINE_GAP = 0


def _make_canvas() -> DiagonalCanvas:
    return DiagonalCanvas(width=CANVAS_W, height=CANVAS_H, delta_x=DELTA_X, delta_y=DELTA_Y)


def _load_font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _render_text_mask() -> Image.Image:
    """Render LINES stacked, centered in the valid band."""
    font = _load_font(FONT_SIZE)
    tmp = Image.new("L", (1, 1))
    d = ImageDraw.Draw(tmp)
    bboxes = [d.textbbox((0, 0), t, font=font) for t in LINES]
    heights = [b[3] - b[1] for b in bboxes]
    total_h = sum(heights) + LINE_GAP * (len(LINES) - 1)

    img = Image.new("L", (CANVAS_W, CANVAS_H), color=0)
    draw = ImageDraw.Draw(img)
    y = BAND_Y_MIN + (BAND_HEIGHT - total_h) // 2
    for line, bb in zip(LINES, bboxes):
        tw = bb[2] - bb[0]
        x = BAND_X_MIN + (BAND_WIDTH - tw) // 2 - bb[0]
        draw.text((x, y - bb[1]), line, fill=255, font=font)
        y += (bb[3] - bb[1]) + LINE_GAP
    return img


_TEXT_MASK = _render_text_mask()


def _paint_band(canvas: DiagonalCanvas, value: int) -> None:
    """Fill the valid projection band at the given brightness."""
    for y in range(BAND_Y_MIN, BAND_Y_MAX + 1):
        for x in range(BAND_X_MIN, BAND_X_MAX + 1):
            canvas.set_pixel(x, y, value)


def _apply_mask(canvas: DiagonalCanvas, mask: Image.Image, scale: float) -> None:
    px = mask.load()
    for y in range(canvas.height):
        for x in range(canvas.width):
            m = px[x, y]
            if m:
                canvas.set_pixel(x, y, int(m * scale))


def _stage_dark(duration_ms: int) -> Iterator[DiagonalCanvas]:
    for _ in range(duration_ms // FRAME_MS):
        yield _make_canvas()


def _stage_wake(duration_ms: int) -> Iterator[DiagonalCanvas]:
    total = duration_ms // FRAME_MS
    for i in range(total):
        c = _make_canvas()
        progress = (i + 1) / total
        head_x = BAND_X_MIN + int(BAND_WIDTH * progress)
        tail = 10
        for x in range(max(BAND_X_MIN, head_x - tail), min(BAND_X_MAX + 1, head_x + 2)):
            d = abs(x - head_x)
            v = max(0, 255 - d * (255 // (tail + 1)))
            for y in range(BAND_Y_MIN, BAND_Y_MAX + 1):
                c.set_pixel(x, y, v)
        yield c


def _stage_text_fade_in(duration_ms: int) -> Iterator[DiagonalCanvas]:
    total = duration_ms // FRAME_MS
    for i in range(total):
        c = _make_canvas()
        progress = (i + 1) / total
        glow = int(40 * (1 - progress))
        if glow > 0:
            _paint_band(c, glow)
        _apply_mask(c, _TEXT_MASK, progress)
        yield c


def _stage_breathe(duration_ms: int) -> Iterator[DiagonalCanvas]:
    total = duration_ms // FRAME_MS
    for i in range(total):
        c = _make_canvas()
        t = (i / FPS) * 2 * math.pi * 0.4
        pulse = 0.7 + 0.3 * (0.5 + 0.5 * math.sin(t))
        _apply_mask(c, _TEXT_MASK, pulse)
        yield c


def _stage_fade_out(duration_ms: int) -> Iterator[DiagonalCanvas]:
    total = duration_ms // FRAME_MS
    for i in range(total):
        c = _make_canvas()
        factor = max(0.0, 1.0 - (i + 1) / total)
        _apply_mask(c, _TEXT_MASK, factor)
        yield c


def frames() -> Iterator[DiagonalCanvas]:
    yield from _stage_dark(300)
    yield from _stage_wake(600)
    yield from _stage_text_fade_in(1200)
    yield from _stage_breathe(4000)
    yield from _stage_fade_out(800)
    yield from _stage_dark(600)
