"""Nesting tree for polygon containment (parent/children/holes)."""

from __future__ import annotations

from shapely.geometry import Polygon as ShapelyPolygon, box as shapely_box


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