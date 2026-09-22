"""Вычисление суммарной площади вложенных замкнутых полилиний с учётом отверстий.

Алгоритм:
1. Выбор LWPOLYLINE (предварительный выбор или через select).
2. Построение дерева вложенности через Shapely (covers).
3. Площадь внешних контуров (чётная глубина) — суммируется.
4. Площадь дыр (нечётная глубина) — вычитается.
5. Вывод: "12345.67 м2 ( 1.23 га )".
"""

from __future__ import annotations

import traceback

from pyrx import Ap, Db, Ed, Ge, command
from shapely.geometry import Polygon as ShapelyPolygon


# ---------------------------------------------------------------------------
# Nesting tree helpers (copied from draw_nomenclature.nesting)
# ---------------------------------------------------------------------------


def _build_nesting_tree(
    shapely_polys: list[ShapelyPolygon],
) -> tuple[dict[int, int | None], dict[int, list[int]]]:
    """Построить parent→children map: родитель = наименьший по площади covering-полигон.

    Использует `covers`, чтобы корректно обрабатывать случай,
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


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


@command(
    name="IGI_GETTOTALAREAOFNESTEDPOLYGONS",
    flags=Ap.CmdFlags.USEPICKSET | Ap.CmdFlags.REDRAW,
)
def get_total_area_of_nested_polygons() -> None:
    """Выбрать замкнутые полилинии и вычислить суммарную площадь с учётом отверстий."""
    print("\n[IGI Tools] Запуск IGI_GETTOTALAREAOFNESTEDPOLYGONS…")

    try:
        # ── Step 1: entity selection ──
        filter = [(Db.DxfCode.kDxfStart, "LWPOLYLINE")]

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

        # ── Step 2: collect closed polylines → Shapely polygons ──
        poly_data: list[ShapelyPolygon] = []
        errors: list[str] = []

        for idx, oid in enumerate(oids):
            pline = Db.Polyline(oid, Db.OpenMode.kForRead)
            try:
                if not pline.isClosed():
                    errors.append(f"Полилиния #{idx + 1} не замкнута — пропущена.")
                    continue

                vertices: list[tuple[float, float]] = []
                for i in range(pline.numVerts()):
                    p = pline.getPoint3dAt(i)
                    vertices.append((p.x, p.y))

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

                poly_data.append(shapely_poly)
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
        parent_map, children_map = _build_nesting_tree(poly_data)

        # ── Step 4: compute total area ──
        total_area = 0.0
        processed_outer = 0

        for idx in range(len(poly_data)):
            depth = _depth_in_tree(parent_map, idx)
            if depth % 2 == 0:
                total_area += poly_data[idx].area
                processed_outer += 1
            else:
                total_area -= poly_data[idx].area

        # ── Step 5: output ──
        if processed_outer == 0:
            print("[IGI Tools] Не найдено внешних контуров для вычисления площади.")
            return

        total_area_ga = total_area / 10000.0
        print(f"\n[IGI Tools] {total_area:.2f} м2 ({total_area_ga:.2f} га)")
        print(f"[IGI Tools] Обработано полигонов: {len(poly_data)}, внешних контуров: {processed_outer}.")

    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")