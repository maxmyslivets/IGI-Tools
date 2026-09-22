"""Geometry helpers: vertex extraction, segment math, cell/polygon intersection."""

from __future__ import annotations

import math

from pyrx import Db, Ge


def _vertex_xy(pline: Db.Polyline) -> list[tuple[float, float]]:
    """XY-вершины LWPOLYLINE в WCS."""
    pts: list[tuple[float, float]] = []
    for i in range(pline.numVerts()):
        p = pline.getPointAtParam(float(i))
        pts.append((p.x, p.y))
    return pts


def _segments(
    vertices: list[tuple[float, float]], closed: bool
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
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
    """Ячейка пересекает полигон. Использует isPointInside (AutoCAD) + пересечение отрезков."""
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
    size: float = 250.0,
) -> list[tuple[float, float]]:
    """Ячейки сетки, пересекающие полигон (выравнивание по 250 м).

    Использует встроенную геометрию AutoCAD + проверку пересечения отрезков.
    """
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