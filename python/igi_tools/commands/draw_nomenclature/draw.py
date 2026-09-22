"""Drawing helpers: cell rectangles and nomenclature labels."""

from __future__ import annotations

from pyrx import Db, Ge

from igi_tools.commands.draw_nomenclature.config import (
    GRID_SIZE,
    TEXT_HEIGHT,
    calculate_nomenclature,
)


def _add_cell_rect(db: Db.Database, x0: float, y0: float, size: float) -> None:
    pline = Db.Polyline(4)
    pline.setDatabaseDefaults(db)
    pline.addVertexAt(0, Ge.Point2d(x0, y0))
    pline.addVertexAt(1, Ge.Point2d(x0 + size, y0))
    pline.addVertexAt(2, Ge.Point2d(x0 + size, y0 + size))
    pline.addVertexAt(3, Ge.Point2d(x0, y0 + size))
    pline.setClosed(True)
    db.addToModelspace(pline)


def _add_label(db: Db.Database, text: str, cx: float, cy: float, height: float) -> None:
    pt = Ge.Point3d(cx, cy, 0.0)
    txt = Db.Text()
    txt.setDatabaseDefaults(db)
    txt.setTextString(text)
    txt.setHeight(height)
    txt.setHorizontalMode(Db.TextHorzMode.kTextCenter)
    txt.setVerticalMode(Db.TextVertMode.kTextVertMid)
    txt.setAlignmentPoint(pt)
    txt.adjustAlignment(db)
    db.addToModelspace(txt)


def draw_cells(
    db: Db.Database,
    cells: list[tuple[float, float]],
    coordinate_system: str = "МСК",
    size: float = GRID_SIZE,
    text_height: float = TEXT_HEIGHT,
) -> int:
    """Нарисовать ячейки и подписи номенклатуры. Возвращает число ячеек."""
    for x0, y0 in cells:
        cx = x0 + size / 2
        cy = y0 + size / 2
        _add_cell_rect(db, x0, y0, size)
        label = calculate_nomenclature(cx, cy, coordinate_system)
        _add_label(db, label, cx, cy, text_height)
    return len(cells)