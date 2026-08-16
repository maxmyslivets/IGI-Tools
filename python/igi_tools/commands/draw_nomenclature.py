"""Номенклатура по замкнутому полигону (сетка 250×250 м) через CADPyRx."""

from __future__ import annotations

import math

from pyrx import Db, Ge, command
from pyrx.ed import prompt as ed_prompt

GRID_SIZE = 250.0
TEXT_HEIGHT = 20.0


def detect_coordinate_system(x: float, y: float) -> str:
    """СК63, если координаты содержат миллионную часть; иначе МСК."""
    if x >= 1_000_000 or y >= 1_000_000:
        return "СК63"
    return "МСК"


def calculate_nomenclature(x: float, y: float, coordinate_system: str) -> str:
    """Номенклатура листа для точки (x, y) в формате YY+XX;NN."""
    if coordinate_system == "СК63":
        x = x % 100000
        y = y % 100000

    x_thousand = int(x / 1000)
    y_thousand = int(y / 1000)
    x_remainder = int((x % 1000) / 250)  # 0-3
    y_remainder = int((y % 1000) / 250)  # 0-3
    square_number = (3 - y_remainder) * 4 + x_remainder + 1
    return f"{y_thousand:02d}+{x_thousand:02d};{square_number:02d}"


def _vertex_xy(pline: Db.Polyline) -> list[tuple[float, float]]:
    """XY-вершины LWPOLYLINE в WCS."""
    pts: list[tuple[float, float]] = []
    for i in range(pline.numVerts()):
        p = pline.getPointAtParam(float(i))
        pts.append((p.x, p.y))
    return pts


def _segments(vertices: list[tuple[float, float]], closed: bool) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Рёбра полигона (включая замыкающее, если closed)."""
    n = len(vertices)
    if n < 2:
        return []
    segs = [(vertices[i], vertices[i + 1]) for i in range(n - 1)]
    if closed and n >= 3:
        segs.append((vertices[-1], vertices[0]))
    return segs


def _point_in_rect(x: float, y: float, x0: float, y0: float, x1: float, y1: float) -> bool:
    return x0 <= x <= x1 and y0 <= y <= y1


def _orient(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _on_segment(
    ax: float, ay: float, bx: float, by: float, cx: float, cy: float, eps: float = 1e-9
) -> bool:
    return (
        min(ax, bx) - eps <= cx <= max(ax, bx) + eps
        and min(ay, by) - eps <= cy <= max(ay, by) + eps
    )


def _segments_intersect(
    a1: tuple[float, float],
    a2: tuple[float, float],
    b1: tuple[float, float],
    b2: tuple[float, float],
) -> bool:
    """Пересечение двух отрезков (включая касание)."""
    o1 = _orient(*a1, *a2, *b1)
    o2 = _orient(*a1, *a2, *b2)
    o3 = _orient(*b1, *b2, *a1)
    o4 = _orient(*b1, *b2, *a2)

    if (o1 > 0 and o2 < 0 or o1 < 0 and o2 > 0) and (
        o3 > 0 and o4 < 0 or o3 < 0 and o4 > 0
    ):
        return True

    if abs(o1) < 1e-9 and _on_segment(*a1, *a2, *b1):
        return True
    if abs(o2) < 1e-9 and _on_segment(*a1, *a2, *b2):
        return True
    if abs(o3) < 1e-9 and _on_segment(*b1, *b2, *a1):
        return True
    if abs(o4) < 1e-9 and _on_segment(*b1, *b2, *a2):
        return True
    return False


def _cell_intersects_polygon(
    x0: float,
    y0: float,
    size: float,
    pline: Db.Polyline,
    vertices: list[tuple[float, float]],
    poly_segs: list[tuple[tuple[float, float], tuple[float, float]]],
) -> bool:
    """Ячейка пересекает полигон (аналог shapely box.intersects)."""
    x1 = x0 + size
    y1 = y0 + size
    corners = (
        (x0, y0),
        (x1, y0),
        (x1, y1),
        (x0, y1),
        (x0 + size / 2, y0 + size / 2),
    )
    for cx, cy in corners:
        if pline.isPointInside(Ge.Point3d(cx, cy, 0.0)):
            return True

    for vx, vy in vertices:
        if _point_in_rect(vx, vy, x0, y0, x1, y1):
            return True

    cell_segs = (
        ((x0, y0), (x1, y0)),
        ((x1, y0), (x1, y1)),
        ((x1, y1), (x0, y1)),
        ((x0, y1), (x0, y0)),
    )
    for cs in cell_segs:
        for ps in poly_segs:
            if _segments_intersect(cs[0], cs[1], ps[0], ps[1]):
                return True
    return False


def compute_cells(
    pline: Db.Polyline,
    vertices: list[tuple[float, float]],
    size: float = GRID_SIZE,
) -> list[tuple[float, float]]:
    """Ячейки сетки, пересекающие полигон (выравнивание по 250 м)."""
    xs = [p[0] for p in vertices]
    ys = [p[1] for p in vertices]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)

    minx_g = math.floor(minx / size) * size
    miny_g = math.floor(miny / size) * size
    maxx_g = math.ceil(maxx / size) * size
    maxy_g = math.ceil(maxy / size) * size

    ncols = int(math.ceil((maxx_g - minx_g) / size))
    nrows = int(math.ceil((maxy_g - miny_g) / size))
    poly_segs = _segments(vertices, closed=True)

    cells: list[tuple[float, float]] = []
    for col in range(ncols):
        x0 = minx_g + col * size
        for row in range(nrows):
            y0 = miny_g + row * size
            if _cell_intersects_polygon(x0, y0, size, pline, vertices, poly_segs):
                cells.append((x0, y0))
    return cells


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
    coordinate_system: str,
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


@command(name="IGI_DRAW_NOMENCLATURE")
def draw_nomenclature() -> None:
    """Выбрать замкнутую полилинию и построить сетку номенклатуры 250×250."""
    pl_id = ed_prompt.entsel(
        "\nВыберите замкнутый полигон (полилинию): ",
        eType=Db.Polyline,
    )
    pline = Db.Polyline(pl_id)

    if not pline.isClosed():
        print("\n[IGI Tools] Нужна замкнутая полилиния. Работа прервана.")
        return

    vertices = _vertex_xy(pline)
    if len(vertices) < 3:
        print("\n[IGI Tools] У полилинии меньше 3 вершин. Работа прервана.")
        return

    minx, miny = min(v[0] for v in vertices), min(v[1] for v in vertices)
    coordinate_system = detect_coordinate_system(minx, miny)
    print(f"\n[IGI Tools] Система координат: {coordinate_system}")

    cells = compute_cells(pline, vertices)
    if not cells:
        print("\n[IGI Tools] Внутри полигона нет ячеек сетки 250x250.")
        return

    count = draw_cells(Db.curDb(), cells, coordinate_system)
    print(f"\n[IGI Tools] Построено ячеек сетки: {count}.")
