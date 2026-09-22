"""Constants and nomenclature calculation."""

from __future__ import annotations

import math

GRID_SIZE = 250.0
TEXT_HEIGHT = 20.0


def _format_yyxx(yy: int, xx: int) -> str:
    """Формат YY+XX с учётом знака: 00+09, 00-01, -01+09, -01-01."""
    yy_part = f"{yy:02d}" if yy >= 0 else f"-{abs(yy):02d}"
    if xx >= 0:
        return f"{yy_part}+{xx:02d}"
    return f"{yy_part}-{abs(xx):02d}"


def detect_coordinate_system(x: float, y: float) -> str:
    """СК63, если координаты содержат миллионную часть; иначе МСК."""
    if x >= 1_000_000 or y >= 1_000_000:
        return "СК63"
    return "МСК"


def calculate_nomenclature(x: float, y: float, coordinate_system: str = "МСК") -> str:
    """Номенклатура листа для точки (x, y) в формате YY+XX;NN."""
    if coordinate_system == "СК63":
        x = x % 100000
        y = y % 100000
    x_thousand = int(math.floor(x / 1000))
    y_thousand = int(math.floor(y / 1000))
    x_rem = int((x - x_thousand * 1000) / 250)  # 0-3
    y_rem = int((y - y_thousand * 1000) / 250)  # 0-3
    square_number = (3 - y_rem) * 4 + x_rem + 1
    return f"{_format_yyxx(y_thousand, x_thousand)};{square_number:02d}"