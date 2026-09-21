"""Импорт ГЗУ (границ землепользования) из GeoJSON через CADPyRx.

Импортирует GeoJSON (полигоны gismap.by и стандартный GeoJSON) в активный чертёж:
  - замкнутые полилинии по внешним контурам и внутренним вырезам;
  - блоки «СП_1.5» (из template.dwg / template.dxf) в каждой вершине каждого кольца;
  - цвет 3 (зелёный), масштаб блоков 0.5.

Только PyRx (Db/Ed), без COM.
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path

from pyrx import Db, Ed, Ge, command

from igi_tools.paths import get_template_path

BLOCK_NAME = "СП_1.5"
BLOCK_COLOR = 3
BLOCK_SCALE = 0.5
POLYLINE_COLOR = 3
LAYER_NAME = "0"


# ---------------------------------------------------------------------------
# Парсинг GeoJSON
# ---------------------------------------------------------------------------


def _load_geojson(file_path: str) -> list[tuple[list[tuple[float, float]], bool]]:
    """Загрузить GeoJSON. Возвращает список (ring, is_hole)."""
    results: list[tuple[list[tuple[float, float]], bool]] = []

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "geometry" in item:
                results.extend(_extract_gismap_rings(item["geometry"]))
            elif isinstance(item, list):
                results.append(([(float(c[0]), float(c[1])) for c in item], False))
        return results

    if not isinstance(data, dict):
        raise ValueError(f"Неожиданный тип GeoJSON: {type(data)}")

    geom_type = data.get("type", "")

    if geom_type == "Feature":
        results.extend(_extract_rings_from_geojson(data.get("geometry", data)))
    elif geom_type == "FeatureCollection":
        for feature in data.get("features", []):
            results.extend(_extract_rings_from_geojson(feature.get("geometry", feature)))
    else:
        results.extend(_extract_rings_from_geojson(data))

    return results


def _extract_gismap_rings(geometry: dict) -> list[tuple[list[tuple[float, float]], bool]]:
    """Кольца формата gismap.by: geometry.rings."""
    results: list[tuple[list[tuple[float, float]], bool]] = []
    if not isinstance(geometry, dict):
        return results

    rings = geometry.get("rings")
    if not rings or not isinstance(rings, list):
        return results

    for i, ring in enumerate(rings):
        if not ring or not isinstance(ring, list):
            continue
        points = [(float(c[0]), float(c[1])) for c in ring]
        results.append((points, i > 0))

    return results


def _extract_rings_from_geojson(
    geojson_obj: dict,
) -> list[tuple[list[tuple[float, float]], bool]]:
    """Кольца из GeoJSON-геометрии (Polygon / MultiPolygon / …)."""
    results: list[tuple[list[tuple[float, float]], bool]] = []
    geom_type = geojson_obj.get("type", "")

    if geom_type in ("Polygon", "LinearRing"):
        coords = geojson_obj.get("coordinates", [])
        if coords:
            if coords[0]:
                results.append(([(float(c[0]), float(c[1])) for c in coords[0]], False))
            for hole in coords[1:]:
                if hole:
                    results.append(([(float(c[0]), float(c[1])) for c in hole], True))

    elif geom_type == "MultiPolygon":
        for polygon in geojson_obj.get("coordinates", []):
            if not polygon:
                continue
            if polygon[0]:
                results.append(([(float(c[0]), float(c[1])) for c in polygon[0]], False))
            for hole in polygon[1:]:
                if hole:
                    results.append(([(float(c[0]), float(c[1])) for c in hole], True))

    elif geom_type == "GeometryCollection":
        for geom in geojson_obj.get("geometries", []):
            results.extend(_extract_rings_from_geojson(geom))

    return results


def _dedupe_closed_ring(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Убрать дублирующую замыкающую вершину (GeoJSON часто повторяет первую)."""
    if len(points) >= 2 and points[0] == points[-1]:
        return points[:-1]
    return points


# ---------------------------------------------------------------------------
# Работа с чертежом (Db)
# ---------------------------------------------------------------------------


def _ensure_layer(db: Db.Database, layer_name: str, color: int) -> Db.ObjectId:
    """Создать слой, если его нет. Вернуть ObjectId слоя."""
    lt = Db.LayerTable(db.layerTableId(), Db.OpenMode.kForRead)
    if lt.has(layer_name):
        return lt.getAt(layer_name)

    lt.upgradeOpen()
    rec = Db.LayerTableRecord()
    rec.setName(layer_name)
    rec.setColor(Db.Color(color))
    return lt.add(rec)


class BlockUnavailableError(RuntimeError):
    """Блок «СП_1.5» недоступен ни в чертеже, ни в шаблоне."""


def _load_template_database(path: Path) -> Db.Database:
    """Загрузить шаблон и закрыть файл ввода."""
    src = Db.Database(False, True)
    if path.suffix.lower() == ".dwg":
        src.readDwgFile(
            str(path),
            Db.DatabaseOpenMode.kForReadAndAllShare,
            False,
            "",
        )
    else:
        src.dxfIn(str(path))
    src.closeInput(True)
    return src


def _get_block_id(db: Db.Database, block_name: str) -> Db.ObjectId | None:
    """Вернуть ObjectId блока или None. Таблица блоков закрывается до выхода."""
    bt = Db.BlockTable(db.blockTableId(), Db.OpenMode.kForRead)
    try:
        if bt.has(block_name):
            return bt.getAt(block_name)
        return None
    finally:
        try:
            bt.close()
        except Exception:
            pass


def _import_block_from_template(db: Db.Database) -> Db.ObjectId:
    """Импортировать определение «СП_1.5» из template.dwg через wblockCloneObjects."""
    template_path = get_template_path()
    if not template_path.is_file():
        raise BlockUnavailableError(
            f"Шаблон не найден:\n{template_path}\n\n"
            f"Нужен template.dwg с блоком «{BLOCK_NAME}», "
            f"либо блок уже должен быть в текущем чертеже."
        )

    src = _load_template_database(template_path)

    src_bt = Db.BlockTable(src.blockTableId(), Db.OpenMode.kForRead)
    try:
        if not src_bt.has(BLOCK_NAME):
            raise BlockUnavailableError(
                f"В шаблоне нет блока «{BLOCK_NAME}»:\n{template_path}"
            )
        src_id = src_bt.getAt(BLOCK_NAME)
    finally:
        try:
            src_bt.close()
        except Exception:
            pass

    id_map = Db.IdMapping()
    src.wblockCloneObjects(
        [src_id],
        db.blockTableId(),
        id_map,
        Db.DuplicateRecordCloning.kDrcReplace,
        False,
    )

    block_id = _get_block_id(db, BLOCK_NAME)
    if block_id is None:
        raise BlockUnavailableError(
            f"Не удалось импортировать блок «{BLOCK_NAME}» из шаблона:\n{template_path}"
        )
    return block_id


def _ensure_block(db: Db.Database) -> Db.ObjectId:
    """Вернуть ObjectId блока «СП_1.5» из чертежа или из шаблона."""
    block_id = _get_block_id(db, BLOCK_NAME)
    if block_id is not None:
        return block_id

    try:
        return _import_block_from_template(db)
    except BlockUnavailableError:
        raise
    except Exception as exc:
        raise BlockUnavailableError(
            f"Ошибка импорта блока «{BLOCK_NAME}» из шаблона:\n{exc}"
        ) from exc


def _create_polyline(
    db: Db.Database,
    points: list[tuple[float, float]],
    layer_id: Db.ObjectId,
) -> Db.Polyline | None:
    """Создать замкнутую лёгкую полилинию и добавить в modelspace."""
    pts = _dedupe_closed_ring(points)
    if len(pts) < 3:
        return None

    pline = Db.Polyline()
    pline.setDatabaseDefaults(db)
    for i, (x, y) in enumerate(pts):
        pline.addVertexAt(i, Ge.Point2d(float(x), float(y)))
    pline.setClosed(True)
    pline.setColorIndex(POLYLINE_COLOR)
    pline.setLayer(layer_id)
    db.addToModelspace(pline)
    return pline


def _create_block_ref(
    db: Db.Database,
    point: tuple[float, float],
    block_id: Db.ObjectId,
    layer_id: Db.ObjectId,
) -> Db.BlockReference:
    """Вставить блок «СП_1.5» в точку."""
    bref = Db.BlockReference(
        Ge.Point3d(float(point[0]), float(point[1]), 0.0),
        block_id,
    )
    bref.setDatabaseDefaults(db)
    bref.setScaleFactors(Ge.Scale3d(BLOCK_SCALE))
    bref.setColorIndex(BLOCK_COLOR)
    bref.setLayer(layer_id)
    db.addToModelspace(bref)
    return bref


# ---------------------------------------------------------------------------
# Основная логика
# ---------------------------------------------------------------------------


def import_gzu(file_path: str) -> dict:
    """Импортировать GeoJSON в текущий чертёж. Возвращает статистику."""
    stats = {"polygons": 0, "holes": 0, "blocks": 0, "vertices": 0, "errors": 0}

    try:
        rings_data = _load_geojson(file_path)
    except Exception as exc:
        print(f"\n[IGI Tools] Не удалось распарсить файл {file_path}: {exc}")
        return {"error": str(exc)}

    if not rings_data:
        print(f"\n[IGI Tools] В файле {file_path} не найдено геометрий.")
        return {"skipped": True}

    db = Db.curDb()
    prev_layer = db.clayer()

    try:
        try:
            block_id = _ensure_block(db)
        except BlockUnavailableError as exc:
            print(f"\n[IGI Tools] {str(exc)}")
            return {"error": str(exc), "aborted": True}

        layer_id = _ensure_layer(db, LAYER_NAME, POLYLINE_COLOR)
        db.setClayer(layer_id)

        for ring, is_hole in rings_data:
            if not ring:
                continue

            pts = _dedupe_closed_ring(ring)
            if len(pts) < 3:
                continue

            try:
                _create_polyline(db, pts, layer_id)
                stats["polygons"] += 1
                if is_hole:
                    stats["holes"] += 1
                stats["vertices"] += len(pts)
            except Exception as exc:
                print(f"\n[IGI Tools] Предупреждение при создании полилинии: {exc}")
                stats["errors"] += 1
                continue

            for point in pts:
                try:
                    _create_block_ref(db, point, block_id, layer_id)
                    stats["blocks"] += 1
                except Exception as exc:
                    print(f"\n[IGI Tools] Предупреждение при добавлении блока: {exc}")
                    stats["errors"] += 1

        print("\n[IGI Tools] Импорт завершён:")
        print(f"  Полигонов: {stats['polygons']}")
        print(f"  Дыр (holes): {stats['holes']}")
        print(f"  Вершин: {stats['vertices']}")
        print(f"  Блоков вставлено: {stats['blocks']}")
        return stats

    except Exception as exc:
        print(f"\n[IGI Tools] Критическая ошибка при импорте: {exc}")
        traceback.print_exc()
        return {"error": str(exc)}
    finally:
        try:
            db.setClayer(prev_layer)
        except Exception:
            pass


def _select_json_file() -> str:
    """Диалог выбора файла через AutoCAD (acedGetFileD)."""
    try:
        path = Ed.Core.getFileD("Импорт ГЗУ — выберите GeoJSON", "", "json", 0)
        return path or ""
    except Exception:
        return ""


@command(name="IGI_GZU_FROM_GEOJSON")
def gzu_from_geojson() -> None:
    """Выбрать GeoJSON и импортировать границы ГЗУ в текущий чертёж."""
    print("\n" + "=" * 60)
    print("[IGI Tools] Импорт ГЗУ — границы из GeoJSON (PyRx)")
    print("=" * 60)

    file_path = _select_json_file()
    if not file_path:
        print("\n[IGI Tools] Выбор файла отменён.")
        return

    print(f"\n[IGI Tools] Выбран файл: {file_path}")
    stats = import_gzu(file_path)

    if stats.get("aborted"):
        print("\n[IGI Tools] Импорт прерван: блок недоступен.")
        return

    if "error" in stats:
        print(f"\n[IGI Tools] Ошибка импорта: {stats['error']}")
        return

    if stats.get("skipped"):
        print("\n[IGI Tools] Геометрии не найдены.")
        return

    print(
        f"\n[IGI Tools] Импорт: {stats.get('polygons', 0)} полигонов, "
        f"{stats.get('blocks', 0)} блоков."
    )
