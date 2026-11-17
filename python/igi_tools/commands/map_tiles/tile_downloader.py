"""Загрузка тайлов с картографических серверов.

Новая архитектура (по мотивам tiles-map-downloader):
  - TileProvider — dataclass-интерфейс провайдера
  - get_default_providers() — фабрика провайдеров
  - Конкурентная загрузка через ThreadPoolExecutor
  - Progress callback как в донорском onProgress
"""

from __future__ import annotations

import math
import traceback
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable


# ---------------------------------------------------------------------------
# TileProvider — dataclass провайдера (аналог донорского TileProvider)
# ---------------------------------------------------------------------------


@dataclass
class TileProvider:
    """Провайдер тайлов (интерфейс, как в доноре)."""
    id: str
    name: str
    url_template: str
    min_zoom: int = 1
    max_zoom: int = 19
    format: str = "png"
    referer: str = ""
    timeout: int = 10

    def get_tile_url(self, x: int, y: int, z: int, lang: str = "ru_RU") -> str:
        """Строит URL тайла."""
        url = self.url_template.replace("{x}", str(x)).replace("{y}", str(y)).replace("{z}", str(z))
        if "{lang}" in url:
            url = url.replace("{lang}", lang)
        return url


# ---------------------------------------------------------------------------
# Провайдеры (аналог TileProviderFactory)
# ---------------------------------------------------------------------------


def get_default_providers() -> list[TileProvider]:
    """Возвращает список доступных провайдеров (аналог TileProviderFactory)."""
    return [
        TileProvider(
            id="google",
            name="Google Satellite",
            url_template="https://mt.google.com/vt/lyrs=y&x={x}&y={y}&z={z}&hl={lang}",
            max_zoom=20,
            format="png",
            referer="https://www.google.com/maps",
        ),
        TileProvider(
            id="yandex",
            name="Yandex Maps (Спутник)",
            url_template="https://core-renderer-tiles.maps.yandex.net/tiles?l=sat&x={x}&y={y}&z={z}&lang={lang}",
            max_zoom=19,
            format="jpg",
            referer="https://yandex.ru/maps",
        ),
    ]


def _get_provider_by_id(provider_id: str) -> TileProvider | None:
    """Находит провайдера по id."""
    for p in get_default_providers():
        if p.id == provider_id:
            return p
    return None


# ---------------------------------------------------------------------------
# Координатные функции (как в доноре src/downloader.ts)
# ---------------------------------------------------------------------------


def lonlat_to_tile(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    """LatLng → Tile XY (Slippy Map / TMS). Аналог донорского latLngToTile."""
    import math
    n = 1 << zoom  # 2**zoom
    # Ограничение lon в [-180, 180]
    lon = max(-180.0, min(180.0, lon))
    # Ограничение lat в [-85.0511, 85.0511] (Web Mercator bounds)
    lat = max(-85.0511, min(85.0511, lat))
    x = int((lon + 180.0) / 360.0 * n)
    y_raw = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    y = int(y_raw)
    # Ограничение допустимых координат тайла [0, n-1]
    x = max(0, min(n - 1, x))
    y = max(0, min(n - 1, y))

    return x, y


def tile_to_latlon(x: int, y: int, zoom: int) -> tuple[float, float]:
    """Tile XY → LatLng (левый верхний угол тайла). Аналог донорского tileToLatLng."""
    n = 1 << zoom
    lon = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / n)))
    lat = math.degrees(lat_rad)
    return lat, lon


def lonlat_to_pixel(lon: float, lat: float, zoom: int) -> tuple[float, float]:
    """Конвертирует координаты в пиксели тайла (256×256)."""
    n = 1 << zoom
    x_pixel = (lon + 180.0) / 360.0 * n * 256.0
    lat_rad = math.radians(lat)
    y_pixel = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n * 256.0
    return x_pixel, y_pixel


# ---------------------------------------------------------------------------
# HTTP загрузка
# ---------------------------------------------------------------------------

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def _fetch_url(url: str, timeout: int = 10, referer: str = "") -> bytes | None:
    """Загружает тайл по URL. Проверяет сигнатуру PNG/JPEG."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": _USER_AGENT,
            "Accept": "image/avif,webp,apng,image/*,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        if referer:
            req.add_header("Referer", referer)

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            img_data = resp.read()

        if not img_data:
            return None

        # Проверка сигнатуры — сервер может отдавать не тот формат что заявлен
        if img_data[:4] == b'\x89PNG':
            return img_data  # PNG — ок
        if img_data[:2] == b'\xff\xd8':
            return img_data  # JPEG — тоже ок
        # Неизвестный формат
        print(f"  [MapTiles] Неизвестный формат изображения: первые байты {img_data[:8].hex()}")
        return None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # тайл не существует — нормально
        print(f"  [MapTiles] HTTP {e.code} для {url}")
        return None
    except urllib.error.URLError as e:
        print(f"  [MapTiles] Ошибка сети: {e.reason}")
        return None
    except Exception:
        traceback.print_exc()
        return None



def get_tiles_in_bbox(
    min_lon: float, min_lat: float, max_lon: float, max_lat: float, zoom: int
) -> list[tuple[int, int, int]]:
    """Возвращает список тайлов (x, y, zoom) для заданного BBox."""
    x_min, y_max = lonlat_to_tile(min_lon, max_lat, zoom)  # северо-запад
    x_max, y_min = lonlat_to_tile(max_lon, min_lat, zoom)  # юго-восток

    # Защита: если x_min > x_max или y_min > y_max — меняем местами
    if x_min > x_max:
        x_min, x_max = x_max, x_min
    if y_min > y_max:
        y_min, y_max = y_max, y_min

    tiles = []
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            tiles.append((x, y, zoom))
    return tiles


def download_tile(
    x: int, y: int, z: int, provider: TileProvider, lang: str = "ru_RU"
) -> bytes | None:
    """Загружает один тайл."""
    url = provider.get_tile_url(x, y, z, lang)
    return _fetch_url(url, provider.timeout, provider.referer)


def download_all_tiles(
    tile_coords: list[tuple[int, int, int]],
    provider: TileProvider,
    progress_callback: Callable[[int, int], None] | None = None,
    max_concurrency: int = 6,
    lang: str = "ru_RU",
) -> dict:
    """
    Загружает все тайлы КОНКУРЕНТНО через ThreadPoolExecutor.
    Аналог донорского downloadTiles с chunk-конкурентностью.

    Возвращает dict:
    {
        "data": {(x, y, z): bytes, ...},
        "failed": [(x, y, z), ...],
    }
    """
    total = len(tile_coords)
    if total == 0:
        return {"data": {}, "failed": []}

    print(f"\n[MapTiles] Загрузка {total} тайлов (конкурентность: {max_concurrency})...")

    tile_data: dict[tuple[int, int, int], bytes] = {}
    failed: list[tuple[int, int, int]] = []
    completed = 0

    def _download_one(coords: tuple[int, int, int]) -> tuple:
        x, y, z = coords
        try:
            data = download_tile(x, y, z, provider, lang)
            return coords, data
        except Exception:
            return coords, None

    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        futures = {executor.submit(_download_one, coords): coords for coords in tile_coords}
        for future in as_completed(futures):
            coords, data = future.result()
            completed += 1
            if data is not None:
                tile_data[coords] = data
            else:
                failed.append(coords)
            if progress_callback:
                progress_callback(completed, total)

    print(f"[MapTiles] Загружено: {len(tile_data)}, ошибок: {len(failed)} из {total}")
    return {"data": tile_data, "failed": failed}


def get_max_zoom_for_bbox(
    bbox: tuple[float, float, float, float],
    tile_provider_id: str,
    max_tiles: int = 64,
) -> int:
    """Определяет максимальный зум, при котором кол-во тайлов не превышает max_tiles."""
    provider = _get_provider_by_id(tile_provider_id)
    max_zoom = provider.max_zoom if provider else 18
    min_zoom = provider.min_zoom if provider else 1
    min_lon, min_lat, max_lon, max_lat = bbox

    for z in range(max_zoom, min_zoom - 1, -1):
        tiles = get_tiles_in_bbox(min_lon, min_lat, max_lon, max_lat, z)
        if len(tiles) <= max_tiles:
            return z
    return max(1, min_zoom)