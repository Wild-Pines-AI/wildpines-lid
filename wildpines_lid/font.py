"""Tiny bitmap font with per-glyph width, upper-case ASCII subset."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Glyph:
    width: int
    rows: list[list[int]]


@dataclass
class BitmapFont:
    height: int
    spacing: int
    default_width: int
    glyphs: dict[str, Glyph]

    def glyph(self, ch: str) -> Glyph:
        return self.glyphs.get(ch.upper(), self.glyphs[" "])

    @property
    def width(self) -> int:
        return self.default_width


def _g(*rows: str) -> Glyph:
    w = len(rows[0])
    return Glyph(width=w, rows=[[1 if c == "#" else 0 for c in row] for row in rows])


WP_FONT = BitmapFont(
    height=5,
    spacing=1,
    default_width=3,
    glyphs={
        " ": _g("   ", "   ", "   ", "   ", "   "),
        "A": _g(" # ", "# #", "###", "# #", "# #"),
        "D": _g("## ", "# #", "# #", "# #", "## "),
        "E": _g("###", "#  ", "###", "#  ", "###"),
        "I": _g("###", " # ", " # ", " # ", "###"),
        "L": _g("#  ", "#  ", "#  ", "#  ", "###"),
        "N": _g("# #", "###", "###", "###", "# #"),
        "P": _g("## ", "# #", "## ", "#  ", "#  "),
        "S": _g(" ##", "#  ", " # ", "  #", "## "),
        "W": _g("#   #", "#   #", "# # #", "## ##", "#   #"),
    },
)

DEFAULT_FONT = WP_FONT
