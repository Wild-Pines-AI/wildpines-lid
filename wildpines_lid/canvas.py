"""Upright canvas for authoring content that renders correctly on the diagonal lid.

The AniMe Vision planar buffer is a diamond lattice — (row, col) pairs in
planar space are NOT in a horizontal line physically. To draw upright text
or images, we author in a rectangular "diagonal canvas" and apply g-helper's
transform:

    plX = (x - y) / 2
    plY = x + y

with optional (deltaX, deltaY) offsets. This is `SetLedDiagonal` in
AnimeMatrixDevice.cs. Only writes where the resulting (plX, plY) lands
inside the valid [FirstX(y), Width(y)) band for that planar row.

Canvas sizes (from g-helper):
- General: 97 x 63   (MaxRows + FullRows) x (MaxCols + FullRows)
- Text:    68 x 39   MaxRows x (MaxRows - FullRows)

We default to 97 x 63 and let callers use smaller.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from . import geometry, protocol

CANVAS_W = geometry.GRID_ROWS + geometry.FULL_ROWS   # 97
CANVAS_H = geometry.GRID_COLS + geometry.FULL_ROWS   # 63
TEXT_CANVAS_W = geometry.GRID_ROWS                   # 68
TEXT_CANVAS_H = geometry.GRID_ROWS - geometry.FULL_ROWS  # 39


class DiagonalCanvas:
    """Upright (x, y) canvas. Top-left = (0,0), x right, y down.

    Use .set_pixel(x, y, v) to draw, then .to_pixels() to get the 810-byte
    planar LED buffer with the diagonal rotation applied.
    """

    def __init__(self, width: int = CANVAS_W, height: int = CANVAS_H,
                 delta_x: int = 0, delta_y: int | None = None) -> None:
        self.width = width
        self.height = height
        # Match g-helper's default for STRIX text: deltaY = height - FullRows/2 - 1 ==> the call
        # site in SetBitmapDiagonal does `deltaY - (FullRows/2) - 1`. We keep the caller's
        # supplied delta_y as the final offset and let them pass the g-helper-style value.
        self._delta_x = delta_x
        self._delta_y = delta_y if delta_y is not None else (height - geometry.FULL_ROWS // 2 - 1)
        self._buf = bytearray(width * height)

    def clear(self) -> None:
        for i in range(len(self._buf)):
            self._buf[i] = 0

    def set_pixel(self, x: int, y: int, value: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self._buf[y * self.width + x] = max(0, min(255, int(value)))

    def get_pixel(self, x: int, y: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self._buf[y * self.width + x]
        return 0

    def fill_rect(self, x: int, y: int, w: int, h: int, value: int) -> None:
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.set_pixel(xx, yy, value)

    def blit_text(self, text: str, x: int, y: int, font, value: int = 255) -> int:
        cur_x = x
        for ch in text:
            g = font.glyph(ch)
            for r in range(font.height):
                for c in range(g.width):
                    if g.rows[r][c]:
                        self.set_pixel(cur_x + c, y + r, value)
            cur_x += g.width + font.spacing
        return cur_x

    def _to_planar_buffer(self) -> bytearray:
        """Apply (x-y)/2, x+y transform from diagonal canvas to the 810-pixel
        planar buffer. Writes with `color > 20` threshold matching g-helper's
        SetBitmapDiagonal behavior (filters bmp antialiasing halos)."""
        pixels = bytearray(geometry.LED_COUNT)
        for y in range(self.height):
            for x in range(self.width):
                v = self._buf[y * self.width + x]
                if v <= 20:
                    continue
                # g-helper SetLedDiagonal: x += deltaX; y -= deltaY
                xx = x + self._delta_x
                yy = y - self._delta_y
                plx = (xx - yy) // 2
                ply = xx + yy
                if xx - yy == -1:
                    plx = -1
                # planar bounds check — same as SetLedPlanar
                if not 0 <= ply < geometry.GRID_ROWS:
                    continue
                first = geometry._first_x(ply)
                width = geometry._width(ply)
                if not first <= plx < width:
                    continue
                idx = geometry._row_start(ply) + (plx - first)
                if 0 <= idx < geometry.LED_COUNT:
                    pixels[idx] = v
        return pixels

    def to_pixels(self) -> bytes:
        return bytes(self._to_planar_buffer())

    def build_frame(self) -> list[bytes]:
        pages = protocol.build_frame_pages(self.to_pixels())
        return pages + [protocol.build_latch()]

    def to_png(self, path: Path | str, scale: int = 8) -> None:
        """Preview the upright canvas (what should appear on the lid)."""
        img = Image.new("L", (self.width * scale, self.height * scale))
        pixels = img.load()
        for y in range(self.height):
            for x in range(self.width):
                v = self._buf[y * self.width + x]
                for dy in range(scale):
                    for dx in range(scale):
                        pixels[x * scale + dx, y * scale + dy] = v
        img.save(str(path))

    def to_planar_preview_png(self, path: Path | str, scale: int = 12) -> None:
        """Preview the planar buffer that will actually be sent — shows what the
        rotated content looks like mapped onto the diamond LED layout."""
        pixels_buf = self._to_planar_buffer()
        # reverse planar (row=ply, col=plx) from the pixel buffer
        img = Image.new("RGB", (geometry.GRID_COLS * scale, geometry.GRID_ROWS * scale))
        img_px = img.load()
        for ply in range(geometry.GRID_ROWS):
            first = geometry._first_x(ply)
            pitch = geometry._pitch(ply)
            start = geometry._row_start(ply)
            for i in range(pitch):
                plx = first + i
                v = pixels_buf[start + i]
                color = (0, v, 0) if v > 0 else (0, 30, 0)
                for dy in range(scale):
                    for dx in range(scale):
                        img_px[plx * scale + dx, ply * scale + dy] = color
        img.save(str(path))
