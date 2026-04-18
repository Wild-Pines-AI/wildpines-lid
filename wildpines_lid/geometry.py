"""LED coordinate mapping for the 810-LED AniMe Vision on G835 (STRIX profile).

Grid: 34 cols x 68 rows, with rows 0-28 rectangular (FullRows=29) and
rows 29-67 tapering to a diamond shape. From g-helper source the row layout:

  Width(y)   = 1 + y/2                      (int division) — pitch in LEDs per row
  FirstX(y)  = ceil(max(0, y-29) / 2)       — leftmost LED column in row y
  Pitch(y)   = Width(y) - FirstX(y)         — number of LEDs in row y

The buffer index of the first LED in row y is cumulative Pitch over prior rows.
"""

from __future__ import annotations

import math
from functools import lru_cache

LED_COUNT = 810
GRID_ROWS = 68
GRID_COLS = 34
FULL_ROWS = 29


@lru_cache(maxsize=None)
def _width(y: int) -> int:
    return 1 + y // 2


@lru_cache(maxsize=None)
def _first_x(y: int) -> int:
    return math.ceil(max(0, y - (FULL_ROWS + 0)) / 2)


@lru_cache(maxsize=None)
def _pitch(y: int) -> int:
    return _width(y) - _first_x(y)


@lru_cache(maxsize=None)
def _row_start(y: int) -> int:
    return sum(_pitch(yy) for yy in range(y))


# Provisional bounding box for the framebuffer. Actual geometry is non-rectangular.
BBOX_ROWS = GRID_ROWS
BBOX_COLS = GRID_COLS


def rc_to_index(row: int, col: int) -> int | None:
    """Map (row, col) in the virtual grid to a linear LED index, or None if the
    cell is outside the lit area (corner cuts, diamond taper).

    This is a FIRST-PASS mapping based on the g-helper geometry functions.
    It will likely need empirical calibration once we can see actual pixels.
    """
    if not 0 <= row < GRID_ROWS:
        return None
    first = _first_x(row)
    pitch = _pitch(row)
    local = col - first
    if not 0 <= local < pitch:
        return None
    return _row_start(row) + local


def total_leds() -> int:
    return sum(_pitch(y) for y in range(GRID_ROWS))
