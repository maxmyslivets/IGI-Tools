"""Склейка тайлов в одно PNG-изображение через Pillow."""

from __future__ import annotations

import io
import traceback
from pathlib import Path

from PIL import Image


def stitch_tiles(
    tile_data: dict[tuple[int, int], bytes],
    tile_coords_list: list[tuple[int, int, int]],
    output_path: str | Path,
) -> dict:
    """
    Склеивает тайлы в одно изображение и сохраняет как PNG.

    tile_data: {(x, y): bytes} — данные тайлов (байты PNG/JPEG)
    tile_coords_list: [(x, y, z), ...] — список всех ожидаемых тайлов (из download_all_tiles)
    output_path: путь для сохранения результата

    Возвращает словарь:
    {
        "path": str,           # путь к сохранённому PNG
        "width": int,          # ширина итогового изображения в пикселях
        "height": int,         # высота
        "tiles_stitched": int, # сколько тайлов склеено
        "tiles_failed": int,   # сколько тайлов не удалось загрузить/декодировать
    }
    """
    if not tile_data:
        raise ValueError("Нет данных тайлов для склейки")

    # Определяем границы тайлов: используем tile_coords_list (если передан)
    # как полный список ожидаемых тайлов, или вычисляем из tile_data.
    if tile_coords_list:
        coords = tile_coords_list  # list[tuple[int, int, int]]
        xs = [t[0] for t in coords]
        ys = [t[1] for t in coords]
    else:
        xs = [x for (x, y) in tile_data.keys()]
        ys = [y for (x, y) in tile_data.keys()]

    if not xs or not ys:
        raise ValueError("Пустые координаты тайлов")

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    cols = max_x - min_x + 1   # количество тайлов по горизонтали
    rows = max_y - min_y + 1   # количество тайлов по вертикали

    tile_size_px = 256  # стандартный размер тайла

    print(f"[MapTiles] Склейка {len(tile_data)} тайлов в PNG ({cols}×{rows})...")

    # Создаём холст
    canvas = Image.new("RGB", (cols * tile_size_px, rows * tile_size_px), color=(255, 255, 255))

    stitched = 0
    failed = 0

    for (x, y), data in tile_data.items():
        col = x - min_x
        row = y - min_y
        if data is None:
            failed += 1
            continue
        try:
            # Открываем изображение из байтов через PIL
            img = Image.open(io.BytesIO(data))
            # Конвертируем в RGB (на случай если JPEG/палитра/P)
            if img.mode != "RGB":
                img = img.convert("RGB")
            # Вставляем в холст
            canvas.paste(img, (col * tile_size_px, row * tile_size_px))
            stitched += 1
        except Exception:
            failed += 1
            traceback.print_exc()

    # Считаем отсутствующие тайлы из tile_coords_list
    if tile_coords_list:
        tile_data_set = set(tile_data.keys())
        for t in tile_coords_list:
            if (t[0], t[1]) not in tile_data_set:
                failed += 1

    if stitched == 0:
        print("[IGI Map Tiles] Ошибка: ни один тайл не был загружен.")
        return {
            "path": None,
            "width": 0,
            "height": 0,
            "tiles_stitched": 0,
            "tiles_failed": failed,
        }

    # Сохраняем через PIL — корректный PNG
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)

    width, height = canvas.size
    print(f"[MapTiles] PNG сохранён: {output_path} ({width}×{height}, {stitched} тайлов)")

    return {
        "path": str(output_path),
        "width": width,
        "height": height,
        "tiles_stitched": stitched,
        "tiles_failed": failed,
    }