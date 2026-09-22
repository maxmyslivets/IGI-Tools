"""Номенклатура по замкнутому полигону (сетка 250×250 м) через CADPyRx."""

from __future__ import annotations

import traceback
from collections import defaultdict

from pyrx import Ap, Db, Ed, Ge, command
from shapely.geometry import Polygon as ShapelyPolygon

from igi_tools.commands.draw_nomenclature.config import (
    GRID_SIZE,
    TEXT_HEIGHT,
    detect_coordinate_system,
    calculate_nomenclature,
)
from igi_tools.commands.draw_nomenclature.geometry import (
    _vertex_xy,
    compute_cells,
)
from igi_tools.commands.draw_nomenclature.nesting import (
    _build_nesting_tree,
    _depth_in_tree,
    _filter_cells_by_holes,
)
from igi_tools.commands.draw_nomenclature.draw import draw_cells


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

        # ── Step 3: detect coordinate system ──
        all_vertices = [v for _, vertices, _ in poly_data for v in vertices]
        minx = min(v[0] for v in all_vertices)
        miny = min(v[1] for v in all_vertices)
        coordinate_system = detect_coordinate_system(minx, miny)
        print(f"[IGI Tools] Определена система координат: {coordinate_system}.")

        # ── Step 4: build nesting tree ──
        shapely_polys = [pd[2] for pd in poly_data]
        parent_map, children_map = _build_nesting_tree(shapely_polys)

        # ── Step 5: check for touching boundaries (parent ↔ hole) ──
        for child_idx, parent_idx in parent_map.items():
            if parent_idx is not None and _depth_in_tree(parent_map, child_idx) % 2 == 1:
                if shapely_polys[parent_idx].touches(shapely_polys[child_idx]):
                    print(
                        f"[IGI Tools] Внимание: границы полилинии #{child_idx + 1} (дыра) "
                        f"касаются внешнего контура #{parent_idx + 1}."
                    )

        # ── Step 6: compute visible cells ──
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

        # ── Step 7: draw ──
        total_cells = draw_cells(db, list(visible_set), coordinate_system)
        processed = len(poly_data)

        print(f"\n[IGI Tools] Обработано полигонов: {processed}, построено ячеек сетки: {total_cells}.")

        # ── Summary: grouped nomenclature list ──
        if visible_set:
            block_map: dict[str, list[int]] = defaultdict(list)
            for x0, y0 in visible_set:
                cx = x0 + GRID_SIZE / 2
                cy = y0 + GRID_SIZE / 2
                label = calculate_nomenclature(cx, cy, coordinate_system)
                block, _, sq_str = label.partition(";")
                if sq_str:
                    block_map[block].append(int(sq_str))
            print(f"\n[IGI Tools] Номенклатуры:")
            for block in sorted(block_map):
                sqs = sorted(block_map[block])
                print(f"{block};{','.join(f'{s:02d}' for s in sqs)}")

    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")