"""Команда IGI_MAP_TILES — загрузка спутниковых тайлов с карты в чертёж.

Поток работы:
  1. Пользователь открывает окно с картой и рисует полигон
  2. По указанному полигону скачиваются тайлы максимального разрешения
  3. Тайлы склеиваются в одно PNG-изображение
  4. Пользователь указывает точку вставки в AutoCAD
  5. Изображение вставляется как RasterImage и сохраняется рядом с DWG
"""

from __future__ import annotations

import math
import os
import time
import traceback


from pyrx import Ap, Db, Ed, Ge, command

from .tile_downloader import (
    download_all_tiles,
    get_default_providers as get_tile_providers,
    get_tiles_in_bbox,
    TileProvider,
)
from .tile_stitcher import stitch_tiles


@command(name="IGI_MAP_TILES")
def map_tiles() -> None:
    """Загрузка спутниковых снимков с карты в текущий чертёж.

    Использование:
      1. В открывшемся окне выбрать тайловый сервер и нарисовать полигон.
      2. Дождаться загрузки и склейки тайлов.
      3. Указать точку вставки в чертеже.
      4. Готово — растровое изображение вставлено.
    """
    try:
        print("\n" + "=" * 60)
        print("[IGI Map Tiles] Загрузка спутниковых тайлов")
        print("=" * 60)

        # ── Проверка wxPython ──
        try:
            import wx  # noqa: F401
        except ImportError:
            print(
                "[IGI Map Tiles] wxPython не найден. "
                "Установите CADPyRx с поддержкой wxPython."
            )
            return

        # ── Шаг 1: Открыть карту (с переключением провайдера внутри) ──
        from .map_dialog import show_map_dialog

        map_data = show_map_dialog()
        if map_data is None or map_data.get("action") != "finish":
            print("[IGI Map Tiles] Отменено пользователем.")
            return

        provider_id = map_data.get("provider", "google")
        polygon = map_data["polygon"]
        bbox = (
            map_data["bbox"]["min_lon"],
            map_data["bbox"]["min_lat"],
            map_data["bbox"]["max_lon"],
            map_data["bbox"]["max_lat"],
        )

        providers = get_tile_providers()
        provider_match = next(
            (p for p in providers if p.id == provider_id),
            None,
        )
        if provider_match is None:
            print(f"[IGI Map Tiles] Провайдер '{provider_id}' не найден.")
            return

        provider_name = provider_match.name
        print(f"\n  Выбран тайловый сервер: {provider_name}")
        print(f"  Полигон: {len(polygon)} вершин")
        print(f"  BBox: {bbox}")

        # ── Шаг 3: Максимальный зум провайдера ──
        zoom = provider_match.max_zoom
        print(f"\n[IGI Map Tiles] Используется макс. зум провайдера: {zoom}")

        tile_coords = get_tiles_in_bbox(
            bbox[0], bbox[1], bbox[2], bbox[3], zoom
        )
        tile_count = len(tile_coords)

        # Вычисляем сетку тайлов для stitcher
        xs = [t[0] for t in tile_coords]
        ys = [t[1] for t in tile_coords]
        if not xs:
            print("[IGI Map Tiles] Ошибка: не удалось вычислить координаты тайлов для заданного BBox.")
            return
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        col_count = max_x - min_x + 1
        row_count = max_y - min_y + 1
        print(f"  Сетка: {col_count}×{row_count} ({tile_count} тайлов)")

        if tile_count > 100:
            print(f"  ВНИМАНИЕ: {tile_count} тайлов — загрузка может занять время.")

        # ── Шаг 4: Проверка доступа — загрузить первый тайл ──
        print("\n[IGI Map Tiles] Загрузка тайлов...")
        # Пробная загрузка первого тайла для диагностики
        if tile_coords:
            from .tile_downloader import download_tile
            x0, y0, z0 = tile_coords[0]
            test_data = download_tile(x0, y0, z0, provider_match)
            if test_data is None:
                print(f"  [MapTiles] Тайл ({z0},{x0},{y0}) не загружен (пустой ответ или не изображение)")
                return

        result = download_all_tiles(
            tile_coords,
            provider_match,
            progress_callback=lambda cur, total: _show_progress(cur, total),
            max_concurrency=6,
        )
        tile_data = result.get("data", {})
        failed = result.get("failed", [])
        if failed:
            print(f"\n  Пропущено тайлов (ошибки): {len(failed)}")
            if len(failed) == tile_count:
                print("  Все тайлы не загружены. Попробуйте другой провайдер.")
                return

        # ── Шаг 5: Склеить в один PNG ──
        print("\n[IGI Map Tiles] Склейка тайлов...")

        # Определить путь сохранения — рядом с DWG
        dwg_path = _get_dwg_dir()
        output_name = f"map_tiles_{int(time.time())}.png"
        output_path = os.path.normpath(os.path.join(dwg_path, output_name))
        print(f"[MapTiles] PNG будет сохранён: {output_path}")

        # tile_data ключи (x,y,z); stitcher ожидает {(x, y): bytes}
        tile_data_xy = {(x, y): data for (x, y, z), data in tile_data.items()}

        result = stitch_tiles(tile_data_xy, tile_coords, output_path)
        print(
            f"  Изображение: {result['width']}×{result['height']} px, "
            f"склеено тайлов: {result['tiles_stitched']}"
        )
        print(f"  Сохранено: {output_path}")

        # ── Шаг 6: Вставка в AutoCAD ──
        _insert_image(output_path, result["width"], result["height"])

        print(
            f"\n[IGI Map Tiles] Готово! Изображение сохранено:\n"
            f"  {output_path}"
        )
        print(f"[MapTiles] PNG сохранён: {output_path}")

    except Exception:
        traceback.print_exc()
        print("[IGI Map Tiles] Ошибка: команда прервана.")


# ---------------------------------------------------------------------------
# Путь к папке с DWG
# ---------------------------------------------------------------------------

def _get_dwg_dir() -> str:
    """Возвращает путь к папке текущего DWG-файла.

    Если чертёж не сохранён — использует %TEMP%/IGI_MapTiles.
    """
    try:
        doc = Ap.curDoc()
        if doc is None:
            return os.environ.get("TEMP", "C:\\Temp")
        db = Db.curDb()
        filename = db.getFilename()
        if filename:
            return os.path.dirname(filename)
    except Exception:
        pass

    # Fallback: временная директория
    temp_dir = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "IGI_MapTiles")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


# ---------------------------------------------------------------------------
# Вставка растрового изображения в AutoCAD
# ---------------------------------------------------------------------------

def _insert_image(
    image_path: str,
    img_width: int,
    img_height: int,
) -> None:
    """Вставляет PNG как RasterImage в текущий чертёж.

    Пользователь указывает точку вставки. Масштаб подбирается так,
    чтобы изображение было видимым (1:1 пиксельные единицы, если не задан
    явный масштаб чертежа).

    Сначала пробуется программное создание RasterImage (через CADPyRx API),
    при неудаче — используется команда AutoCAD _.IMAGEATTACH.
    """
    import os  # noqa: F811 — уже импортирован в начале модуля

    # Проверить существование файла изображения
    if not os.path.isfile(image_path):
        print(f"[IGI Map Tiles] Файл изображения не найден: {image_path}")
        return

    db = Db.curDb()

    # ── Запрос точки вставки ──
    res, ins_pt = Ed.Editor.getPoint("\nУкажите точку вставки изображения: ")
    if res != Ed.PromptStatus.eOk:
        print("[IGI Map Tiles] Вставка отменена.")
        return

    # ── Запрос масштаба ──
    res, scale = Ed.Editor.getDist(
        ins_pt, "\nМасштаб (ширина изображения в единицах чертежа): "
    )
    if res != Ed.PromptStatus.eOk:
        print("[IGI Map Tiles] Масштаб не задан — используется 1:1.")
        scale = float(img_width)  # Приблизительный масштаб

    # ── Запрос угла поворота ──
    res, angle = Ed.Editor.getAngle(
        ins_pt, "\nУгол поворота <0>: "
    )
    if res != Ed.PromptStatus.eOk:
        angle = 0.0

    # ── Пытаемся программно, с запасным вариантом ──
    success = _insert_image_programmatic(
        db, image_path, img_width, img_height, ins_pt, scale, angle,
    )

    if not success:
        _insert_image_via_command(
            image_path, ins_pt, scale, angle,
        )


def _insert_image_programmatic(
    db: Db.Database,
    image_path: str,
    img_width: int,
    img_height: int,
    ins_pt: Ge.Point3d,
    scale: float,
    angle: float,
) -> bool:
    """Программное создание RasterImage через CADPyRx API.

    Возвращает True при успехе, False — при ошибке.
    """
    # ── Создание RasterImageDef ──
    img_def_id = _get_or_create_image_def(
        db, image_path, img_width, img_height,
    )
    if img_def_id is None:
        print("[IGI Map Tiles] Не удалось создать определение изображения.")
        return False

    # ── Создание RasterImage ──
    try:
        # RasterImage
        img_ent = Db.RasterImage()
        img_ent.setDatabaseDefaults(db)
        img_ent.setImageDefId(img_def_id)

        # Позиция и ориентация через setOrientation
        u_vec = Ge.Vector3d(scale, 0.0, 0.0)  # ось X = ширина
        v_vec = Ge.Vector3d(
            0.0, scale * img_height / img_width, 0.0,
        )  # ось Y = высота
        if angle != 0.0:
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            u_vec = Ge.Vector3d(scale * cos_a, scale * sin_a, 0.0)
            v_vec = Ge.Vector3d(
                -scale * img_height / img_width * sin_a,
                 scale * img_height / img_width * cos_a,
                 0.0,
            )
        img_ent.setOrientation(ins_pt, u_vec, v_vec)

        # Вставить в modelspace
        db.addToModelspace(img_ent)

        # ── Принудительная активация изображения ──
        # 1. Показать само изображение (не только рамку)
        try:
            img_ent.setShowImage(True)
        except AttributeError:
            try:
                img_ent.setShowImage(1)
            except AttributeError:
                pass

        # 2. Рамка изображения (1 = показать)
        try:
            img_ent.setImageFrame(1)
        except AttributeError:
            try:
                img_ent.setImageFrame(True)
            except AttributeError:
                pass

        # 3. Системные переменные
        try:
            Ed.Core.setVar("IMAGEFRAME", 1)
            Ed.Core.setVar("IMAGEHIDE", 0)
        except Exception:
            pass

        # 4. Регенирация чертежа для отображения
        try:
            Ed.Core.regen()
        except Exception:
            pass

        # 5. Принудительная перезагрузка всех изображений в чертеже
        try:
            Ed.Editor.command("_.IMAGERELOAD", "_ALL")
        except Exception:
            pass

        # ── Диагностика после вставки RasterImage ──
        print(f"[MapTiles] RasterImage создан:")
        print(f"  ObjectId: {img_ent.id()}")
        print(f"  Position: ({img_ent.position().x:.2f}, {img_ent.position().y:.2f})")
        print(f"  Width/Height: {img_ent.imageWidth()} × {img_ent.imageHeight()}")

        print(
            f"[IGI Map Tiles] Изображение вставлено: "
            f"масштаб {scale:.2f}, поворот {angle:.2f} рад"
        )
        return True
    except Exception as exc:
        print(f"[IGI Map Tiles] Программная вставка не удалась: {exc}")
        print("[IGI Map Tiles] Пробую вставку через команду AutoCAD...")
        return False


def _insert_image_via_command(
    image_path: str,
    ins_pt: Ge.Point3d,
    scale: float,
    angle: float,
) -> None:
    """Вставка растрового изображения через стандартную команду AutoCAD
    _.IMAGEATTACH. Этот способ всегда работает, поскольку использует
    собственный механизм AutoCAD.
    """
    deg_angle = math.degrees(angle)
    try:
        # _.IMAGEATTACH <имя_файла> <точка> <масштаб> <угол>
        cmd = (
            f"_.-IMAGEATTACH \"{image_path}\" "
            f"{ins_pt.x},{ins_pt.y} "
            f"{scale} "
            f"{deg_angle}"
        )
        Ed.Editor.command(cmd)
        print(
            f"[IGI Map Tiles] Изображение вставлено через IMAGEATTACH: "
            f"масштаб {scale:.2f}, поворот {deg_angle:.1f}°"
        )
    except Exception as exc:
        print(f"[IGI Map Tiles] Ошибка вставки через IMAGEATTACH: {exc}")
        # Последняя попытка — через строковый API документа
        try:
            doc = Ap.curDoc()
            doc.sendStringToExecute(
                f"_.-IMAGEATTACH \"{image_path}\" "
                f"{ins_pt.x},{ins_pt.y} {scale} {deg_angle} ",
                False, False,
            )
            print(
                "[IGI Map Tiles] Команда IMAGEATTACH отправлена "
                "в очередь документа."
            )
        except Exception as exc2:
            print(f"[IGI Map Tiles] Не удалось вставить изображение: {exc2}")


def _get_or_create_image_def(
    db: Db.Database,
    image_path: str,
    img_width: int,
    img_height: int,
) -> Db.ObjectId | None:
    """Создаёт или находит RasterImageDef для указанного файла.

    Важно: после создания определения вызывается img_def.load()
    для принудительной загрузки данных изображения в память AutoCAD.
    """
    import os  # noqa: F811

    if not os.path.isfile(image_path):
        print(f"[IGI Map Tiles] Файл не найден: {image_path}")
        return None

    try:
        # Получить или создать словарь ISM_RASTER_IMAGE_DICT
        img_dict_id = Db.RasterImageDef.imageDictionary(db)
        if img_dict_id.isNull():
            img_dict_id = Db.RasterImageDef.createImageDictionary(db)

        # Проверить, нет ли уже такого определения (по sourceFileName)
        img_dict = Db.Dictionary(img_dict_id, Db.OpenMode.kForRead)
        existing_dict = img_dict.asDict()
        for name_in_dict, def_id_in_dict in existing_dict.items():
            try:
                existing_def = Db.RasterImageDef(def_id_in_dict, Db.OpenMode.kForRead)
                src = existing_def.sourceFileName()
                existing_def.close()
                if src and os.path.normpath(src) == os.path.normpath(image_path):
                    img_dict.close()
                    return def_id_in_dict
            except Exception:
                continue
        img_dict.close()

        # Создать новое определение
        img_def = Db.RasterImageDef()
        img_def.setSourceFileName(image_path)

        # ПРИНУДИТЕЛЬНАЯ ЗАГРУЗКА: вызываем load() чтобы AutoCAD
        # прочитал данные изображения в ISM (Image Services Manager)
        try:
            img_def.load()
            print(f"[MapTiles] RasterImageDef.load() успешно загружен")
        except AttributeError:
            # load() может отсутствовать в некоторых версиях CADPyRx
            print(f"[MapTiles] RasterImageDef.load() не найден — продолжаем")
        except Exception as load_err:
            print(f"[MapTiles] RasterImageDef.load() warning: {load_err}")

        try:
            img_def.setImageWidth(img_width)
            img_def.setImageHeight(img_height)
        except Exception:
            pass

        # Уникальное имя через suggestName
        img_dict_w = Db.Dictionary(img_dict_id, Db.OpenMode.kForWrite)
        name = Db.RasterImageDef.suggestName(img_dict_w, "map_tiles")
        img_dict_w.setAt(name, img_def)
        img_dict_w.close()

        return img_def.objectId()

    except Exception as exc:
        print(f"[IGI Map Tiles] Ошибка создания RasterImageDef: {exc}")
        return None


# ---------------------------------------------------------------------------
# Прогресс
# ---------------------------------------------------------------------------

def _show_progress(current: int, total: int) -> None:
    """Показывает прогресс загрузки в консоли AutoCAD."""
    if total <= 0:
        return
    pct = current * 100 // total
    bar_len = 30
    filled = pct * bar_len // 100
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r  [{bar}] {pct}% ({current}/{total})", end="", flush=True)
    if current >= total:
        print()