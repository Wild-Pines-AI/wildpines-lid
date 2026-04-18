"""Grayscale framebuffer with drawing primitives.

Renders to a 2D 34x68 grid, packs to an 810-byte pixel buffer using the
geometry module's rc_to_index mapping, then protocol.build_frame_pages +
build_latch ship it to the lid.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from . import geometry, protocol


class Framebuffer:
    def __init__(self, rows: int | None = None, cols: int | None = None) -> None:
        self.rows = rows or geometry.GRID_ROWS
        self.cols = cols or geometry.GRID_COLS
        self._buf = bytearray(self.rows * self.cols)

    def clear(self) -> None:
        for i in range(len(self._buf)):
            self._buf[i] = 0

    def set(self, row: int, col: int, value: int) -> None:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self._buf[row * self.cols + col] = max(0, min(255, int(value)))

    def get(self, row: int, col: int) -> int:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self._buf[row * self.cols + col]
        return 0

    def fill_rect(self, row: int, col: int, h: int, w: int, value: int) -> None:
        for r in range(row, row + h):
            for c in range(col, col + w):
                self.set(r, c, value)

    def blit_text(self, text: str, row: int, col: int, font, value: int = 255) -> int:
        x = col
        for ch in text:
            g = font.glyph(ch)
            for r in range(font.height):
                for c in range(g.width):
                    if g.rows[r][c]:
                        self.set(row + r, x + c, value)
            x += g.width + font.spacing
        return x

    def to_png(self, path: Path | str, scale: int = 12) -> None:
        img = Image.new("RGB", (self.cols * scale, self.rows * scale))
        pixels = img.load()
        for r in range(self.rows):
            for c in range(self.cols):
                mapped = geometry.rc_to_index(r, c) is not None
                if mapped:
                    v = self._buf[r * self.cols + c]
                    color = (0, v, 0) if v > 0 else (0, 30, 0)
                else:
                    color = (25, 0, 0)
                for dy in range(scale):
                    for dx in range(scale):
                        pixels[c * scale + dx, r * scale + dy] = color
        img.save(str(path))

    def to_pixels(self) -> bytes:
        pixels = bytearray(geometry.LED_COUNT)
        for r in range(self.rows):
            for c in range(self.cols):
                idx = geometry.rc_to_index(r, c)
                if idx is None:
                    continue
                pixels[idx] = self._buf[r * self.cols + c]
        return bytes(pixels)

    def build_frame(self) -> list[bytes]:
        pages = protocol.build_frame_pages(self.to_pixels())
        return pages + [protocol.build_latch()]


def measure_text(text: str, font) -> int:
    total = 0
    for i, ch in enumerate(text):
        total += font.glyph(ch).width
        if i < len(text) - 1:
            total += font.spacing
    return total
