"""Номенклатура по замкнутому полигону (сетка 250×250 м) через CADPyRx."""

from __future__ import annotations

import math
import traceback

from pyrx import Ap, Db, Ed, Ge, command
from shapely.geometry import Polygon as ShapelyPolygon, box as shapely_box

GRID_SIZE = 250.0
TEXT_HEIGHT = 20.0


def _format_yyxx(yy: int, xx: int) -> str:
    """Формат YY+XX с учётом знака: 00+09, 00-01, -01+09, -01-01."""
    yy_part = f"{yy:02d}" if yy >= 0 else f"-{abs(yy):02d}"
    if xx >= 0:
        return f"{yy_part}+{xx:02d}"
    return f"{yy_part}-{abs(xx):02d}"


def calculate_nomenclature(x: float, y: float) -> str:
    """Номенклатура листа для точки (x, y) в формате YY+XX;NN."""
    x_thousand = int(math.floor(x / 1000))
    y_thousand = int(math.floor(y / 1000))
    # within-block coordinate in [0, 1000)
    x_rem = int((x - x_thousand * 1000) / 250)  # 0-3
    y_rem = int((y - y_thousand * 1000) / 250)  # 0-3
    square_number = (3 - y_rem) * 4 + x_rem + 1
    return f"{_format_yyxx(y_thousand, x_thousand)};{square_number:02d}"


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
    size: float = GRID_SIZE,
) -> list[tuple[float, float]]:
    """Ячейки сетки, пересекающие полигон (выравнивание по 250 м).
    Использует встроенную геометрию AutoCAD + проверку пересечения отрезков."""
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


def _build_nesting_tree(
    shapely_polys: list[ShapelyPolygon],
) -> tuple[dict[int, int | None], dict[int, list[int]]]:
    """Построить parent→children map: родитель = наименьший по площади covering-полигон.

    Использует `covers` (не `contains`), чтобы корректно обрабатывать случай,
    когда граница дыры касается границы внешнего контура.

    Возвращает (parent_map, children_map).
    """
    n = len(shapely_polys)
    parent_of: dict[int, int | None] = {i: None for i in range(n)}

    for j in range(n):
        candidates = []
        for i in range(n):
            if i == j:
                continue
            if shapely_polys[i].covers(shapely_polys[j]) and not shapely_polys[i].equals_exact(
                shapely_polys[j], 1e-3
            ):
                candidates.append(i)
        if candidates:
            # наименьший по площади = прямой предок
            parent_of[j] = min(candidates, key=lambda k: shapely_polys[k].area)

    children_of: dict[int, list[int]] = {i: [] for i in range(n)}
    for child, parent in parent_of.items():
        if parent is not None:
            children_of[parent].append(child)

    return parent_of, children_of


def _depth_in_tree(parent_map: dict[int, int | None], idx: int) -> int:
    """Глубина узла в дереве вложенности. 0 = самый внешний."""
    depth = 0
    current = parent_map.get(idx)
    while current is not None:
        depth += 1
        current = parent_map.get(current)
    return depth


def _filter_cells_by_holes(
    cells: list[tuple[float, float]],
    hole_polys: list[ShapelyPolygon],
    size: float,
) -> list[tuple[float, float]]:
    """Исключить ячейки, целиком накрытые дырой.

    Ячейка удаляется ТОЛЬКО если hole.contains(box) — дыра полностью содержит
    bounding box ячейки. Если ячейка частично выходит за пределы дыры (попадает
    на чётную глубину), она сохраняется.
    """
    if not hole_polys:
        return cells[:]

    result: list[tuple[float, float]] = []
    for x0, y0 in cells:
        box = shapely_box(x0, y0, x0 + size, y0 + size)
        excluded = False
        for hole in hole_polys:
            if hole.contains(box):
                excluded = True
                break
        if not excluded:
            result.append((x0, y0))
    return result


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
    size: float = GRID_SIZE,
    text_height: float = TEXT_HEIGHT,
) -> int:
    """Нарисовать ячейки и подписи номенклатуры. Возвращает число ячеек."""
    for x0, y0 in cells:
        cx = x0 + size / 2
        cy = y0 + size / 2
        _add_cell_rect(db, x0, y0, size)
        label = calculate_nomenclature(cx, cy)
        _add_label(db, label, cx, cy, text_height)
    return len(cells)


@command(name="IGI_DRAW_NOMENCLATURE", flags=Ap.CmdFlags.USEPICKSET | Ap.CmdFlags.REDRAW)
def draw_nomenclature() -> None:
    """Выбрать замкнутые полилинии и построить сетку номенклатуры 250×250."""
    db = Db.curDb()

    try:
        # ── Step 1: entity selection ──
        filter = [(Db.DxfCode.kDxfStart, "LWPOLYLINE")]

        # Try implied selection (pre-selected objects) first
        impl_status, impl_ss = Ed.Editor.selectImplied()
        if impl_status == Ed.PromptStatus.eOk and impl_ss.size() > 0:
            all_ids = impl_ss.toList()
            oids = []
            for oid in all_ids:
                ent = Db.Entity(oid, Db.OpenMode.kForRead)
                try:
                    if ent.isDerivedFrom(Db.Polyline.desc()):
                        oids.append(oid)
                finally:
                    ent.close()
            if not oids:
                print("[IGI Tools] Среди предварительно выбранных объектов нет полилиний.")
                return
            print(f"[IGI Tools] Найдено предварительно выбранных объектов: {len(oids)}.")
        else:
            print("\nВыберите замкнутые полилинии...")
            res = Ed.Editor.select(filter)
            if res[0] != Ed.PromptStatus.eOk:
                print("[IGI Tools] Выбор отменён.")
                return
            ss = res[1]
            if ss.size() == 0:
                print("[IGI Tools] Объекты не найдены.")
                return
            oids = ss.toList()

        # ── Step 2: collect closed polylines and build Shapely polygons ──
        poly_data: list[tuple[Db.ObjectId, list[tuple[float, float]], ShapelyPolygon]] = []
        errors: list[str] = []

        for idx, oid in enumerate(oids):
            pline = Db.Polyline(oid, Db.OpenMode.kForRead)
            try:
                if not pline.isClosed():
                    errors.append(f"Полилиния #{idx + 1} не замкнута — пропущена.")
                    continue
                vertices = _vertex_xy(pline)
                if len(vertices) < 3:
                    errors.append(f"Полилиния #{idx + 1} имеет менее 3 вершин — пропущена.")
                    continue
                shapely_poly = ShapelyPolygon(vertices)
                if not shapely_poly.is_valid:
                    errors.append(
                        f"Полилиния #{idx + 1} имеет самопересечение "
                        f"или некорректную геометрию — пропущена."
                    )
                    continue
                poly_data.append((oid, vertices, shapely_poly))
            except Exception as e:
                errors.append(f"Полилиния #{idx + 1}: ошибка построения геометрии — {e}.")
            finally:
                pline.close()

        for err in errors:
            print(f"[IGI Tools] {err}")

        if not poly_data:
            print("[IGI Tools] Не найдено ни одной корректной замкнутой полилинии.")
            return

        # ── Step 3: build nesting tree ──
        shapely_polys = [pd[2] for pd in poly_data]
        parent_map, children_map = _build_nesting_tree(shapely_polys)

        # ── Step 4: check for touching boundaries (parent ↔ hole) ──
        for child_idx, parent_idx in parent_map.items():
            if parent_idx is not None and _depth_in_tree(parent_map, child_idx) % 2 == 1:
                if shapely_polys[parent_idx].touches(shapely_polys[child_idx]):
                    print(
                        f"[IGI Tools] Внимание: границы полилинии #{child_idx + 1} (дыра) "
                        f"касаются внешнего контура #{parent_idx + 1}."
                    )

        # ── Step 5: compute visible cells ──
        visible_set: set[tuple[float, float]] = set()

        for idx, (oid, vertices, _) in enumerate(poly_data):
            depth = _depth_in_tree(parent_map, idx)
            if depth % 2 != 0:
                continue  # нечётная глубина = дыра — пропускаем

            pline = Db.Polyline(oid, Db.OpenMode.kForRead)
            try:
                cells = compute_cells(pline, vertices)
            except Exception as exc:
                print(f"[IGI Tools] Ошибка в compute_cells для полилинии #{idx + 1}: {exc}")
                continue
            finally:
                pline.close()

            # дети с нечётной глубиной = дыры этого полигона
            hole_children = [
                child
                for child in children_map.get(idx, [])
                if _depth_in_tree(parent_map, child) % 2 == 1
            ]
            hole_polys = [shapely_polys[child] for child in hole_children]
            filtered = _filter_cells_by_holes(cells, hole_polys, GRID_SIZE)

            for cell in filtered:
                visible_set.add(cell)

        # ── Step 6: draw ──
        total_cells = draw_cells(db, list(visible_set))
        processed = len(poly_data)

        print(f"\n[IGI Tools] Обработано полигонов: {processed}, построено ячеек сетки: {total_cells}.")

    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")