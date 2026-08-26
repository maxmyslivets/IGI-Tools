"""Create buffer polygons around lines and polylines using Shapely."""

from __future__ import annotations

import traceback

from pyrx import Ap, command, Db, Ed, Ge
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union


# ---------------------------------------------------------------------------
# Entity → coordinate extraction
# ---------------------------------------------------------------------------


def _entity_to_coords(ent: Db.Entity) -> list[tuple[float, float]]:
    """Extract [(x, y), ...] from a Line or Polyline."""
    coords: list[tuple[float, float]] = []
    if ent.isDerivedFrom(Db.Line.desc()):
        line = Db.Line.cast(ent)
        coords.append((line.startPoint().x, line.startPoint().y))
        coords.append((line.endPoint().x, line.endPoint().y))
    elif ent.isDerivedFrom(Db.Polyline.desc()):
        pl = Db.Polyline.cast(ent)
        n = pl.numVerts()
        for i in range(n):
            p = pl.getPoint3dAt(i)
            coords.append((p.x, p.y))
    return coords


# ---------------------------------------------------------------------------
# Shapely buffer
# ---------------------------------------------------------------------------


def _shapely_buffer(
    coords: list[tuple[float, float]], half_buf: float, is_closed: bool
) -> Polygon | None:
    """Create a buffered polygon using Shapely.
    
    Lines and open polylines use square caps and miter joins.
    Closed polylines use miter joins only (no caps).
    """
    if len(coords) < 2:
        return None
    if is_closed and len(coords) >= 3:
        geom = Polygon(coords)
        outer = geom.buffer(half_buf, join_style="mitre", mitre_limit=2.0)
        inner = geom.buffer(-half_buf, join_style="mitre", mitre_limit=2.0)
        if inner is not None and not inner.is_empty:
            return outer.difference(inner)
        return outer
    else:
        geom = LineString(coords)
        return geom.buffer(
            half_buf, cap_style="square", join_style="mitre", mitre_limit=2.0
        )


def _extract_polygons(geom) -> list[Polygon]:
    """Extract Polygon(s) from a Shapely geometry, handling MultiPolygon."""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type == "MultiPolygon":
        return list(geom.geoms)
    return []


# ---------------------------------------------------------------------------
# Shapely → AutoCAD conversion
# ---------------------------------------------------------------------------


def _polygon_to_autocad(poly: Polygon, db: Db.Database) -> list[Db.ObjectId]:
    """Convert a Shapely Polygon to closed AutoCAD Polylines
    (exterior ring + interior rings for holes).
    """
    oids: list[Db.ObjectId] = []

    # Exterior ring
    ext_coords = list(poly.exterior.coords)
    if len(ext_coords) >= 4:
        pts = ext_coords[:-1]  # skip closing repeat
        pline = Db.Polyline()
        pline.setDatabaseDefaults(db)
        for i, (x, y) in enumerate(pts):
            pline.addVertexAt(i, Ge.Point2d(x, y))
        pline.setClosed(True)
        oids.append(db.addToModelspace(pline))

    # Interior rings (holes)
    for interior in poly.interiors:
        int_coords = list(interior.coords)
        if len(int_coords) >= 4:
            pts = int_coords[:-1]  # skip closing repeat
            pline = Db.Polyline()
            pline.setDatabaseDefaults(db)
            for i, (x, y) in enumerate(pts):
                pline.addVertexAt(i, Ge.Point2d(x, y))
            pline.setClosed(True)
            oids.append(db.addToModelspace(pline))

    return oids


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


@command(name="IGI_BUFFER_POLY", flags=Ap.CmdFlags.USEPICKSET | Ap.CmdFlags.REDRAW)
def buffer_poly() -> None:
    """Создаёт буферные полигоны вокруг линий и полилиний (Shapely).

    Использование:
      1. Выбрать линии и/или полилинии.
      2. Задать ширину буфера.
      3. Для каждого объекта создаётся замкнутый полигон-буфер.
    """
    db = Db.curDb()
    ed = Ed.Editor()

    try:
        # ── Step 1: entity selection ──
        filter = [(Db.DxfCode.kDxfStart, "LINE,LWPOLYLINE")]

        # Try implied selection (pre-selected objects) first
        impl_status, impl_ss = Ed.Editor.selectImplied()
        if impl_status == Ed.PromptStatus.eOk and impl_ss.size() > 0:
            # Filter pre-selected objects — keep only LINE/LWPOLYLINE
            all_ids = impl_ss.toList()
            oids = []
            for oid in all_ids:
                ent = Db.Entity(oid, Db.OpenMode.kForRead)
                try:
                    if ent.isDerivedFrom(Db.Line.desc()) or ent.isDerivedFrom(Db.Polyline.desc()):
                        oids.append(oid)
                finally:
                    ent.close()
            if not oids:
                print("[IGI Tools] Среди предварительно выбранных объектов нет линий или полилиний.")
                return
            print(f"[IGI Tools] Найдено предварительно выбранных объектов: {len(oids)}.")
        else:
            # Fall back to prompt-based selection
            print("\nВыберите линии и полилинии...")
            res = Ed.Editor.select(filter)
            if res[0] != Ed.PromptStatus.eOk:
                print("[IGI Tools] Выбор отменён.")
                return

            ss = res[1]
            if ss.size() == 0:
                print("[IGI Tools] Объекты не найдены.")
                return
            oids = ss.toList()

        # ── Step 2: buffer distance ──
        res_dist = ed.getDist("\nВведите расстояние буфера: ")
        if res_dist[0] != Ed.PromptStatus.eOk:
            print("[IGI Tools] Ввод расстояния отменён.")
            return

        buffer_dist = res_dist[1]
        if buffer_dist <= 0.0:
            print("[IGI Tools] Расстояние должно быть положительным.")
            return
        half_buf = buffer_dist / 2.0

        # ── Step 3: process each entity ──
        all_polygons: list[Polygon] = []
        processed = 0

        for oid in oids:
            ent = Db.Entity(oid, Db.OpenMode.kForRead)
            try:
                coords = _entity_to_coords(ent)
                if len(coords) < 2:
                    continue
                pl = (
                    Db.Polyline.cast(ent)
                    if ent.isDerivedFrom(Db.Polyline.desc())
                    else None
                )
                is_closed = pl.isClosed() if pl else False
                geom = _shapely_buffer(coords, half_buf, is_closed)
                polys = _extract_polygons(geom)
                all_polygons.extend(polys)
                processed += 1
            except Exception as exc:
                print(f"[IGI Tools] Ошибка обработки объекта: {exc}")
            finally:
                ent.close()

        if not all_polygons:
            print("[IGI Tools] Не удалось создать ни одного буфера.")
            return

        # ── Step 4: union ──
        if len(all_polygons) > 1:
            print(f"[IGI Tools] Объединение {len(all_polygons)} буферов...")
            unioned = unary_union(all_polygons)
            result_polys = _extract_polygons(unioned)
        else:
            result_polys = all_polygons

        # ── Step 5: convert to AutoCAD ──
        created = 0
        for poly in result_polys:
            new_oids = _polygon_to_autocad(poly, db)
            created += len(new_oids)

        # ── Step 6: ask whether to delete originals ──
        ed.initGet(0, "Да Нет")
        kw_res = ed.getKword(
            "\nУдалить исходные линии? [Да/Нет] <Нет>: "
        )
        if kw_res[0] == Ed.PromptStatus.eOk and kw_res[1] == "Да":
            deleted = 0
            for oid in oids:
                try:
                    ent = Db.Entity(oid, Db.OpenMode.kForWrite)
                    ent.erase(True)
                    ent.close()
                    deleted += 1
                except Exception:
                    pass
            print(f"[IGI Tools] Удалено исходных объектов: {deleted}.")

        print(
            f"[IGI Tools] Обработано объектов: {processed}, "
            f"создано буферных полигонов: {created}."
        )

    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")