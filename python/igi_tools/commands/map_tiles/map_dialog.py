"""wx-диалог с интерактивной картой для выбора полигона.

Использует wx.html2.WebView с Leaflet.js для отображения карты
и рисования полигона пользователем.
"""

from __future__ import annotations

import json
import os
import threading
import time
import traceback

import wx
import wx.html2


# ---------------------------------------------------------------------------
# Конфигурация провайдеров для JavaScript
# ---------------------------------------------------------------------------

_TILE_PROVIDERS_JS = r"""
var tileProviders = {
    "google": {
        "name": "Google",
        "url": "https://mt.google.com/vt/lyrs=y&x={x}&y={y}&z={z}&hl=ru_RU",
        "maxZoom": 20,
        "attribution": "\u00a9 Google"
    },
    "yandex": {
        "name": "Yandex",
        "url": "https://sat01.maps.yandex.net/tiles?l=sat&x={x}&y={y}&z={z}&lang=ru_RU",
        "maxZoom": 19,
        "attribution": "\u00a9 \u042f\u043d\u0434\u0435\u043a\u0441 \u041a\u0430\u0440\u0442\u044b"
    }
};
"""


# ---------------------------------------------------------------------------
# HTML-шаблон карты на Leaflet.js
# ---------------------------------------------------------------------------

_LEAFLET_HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IGI Map Tiles</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 100%; height: 100%; overflow: hidden; }
  body { font-family: 'Segoe UI', sans-serif; }

  #header {
    height: 44px;
    background: #2c3e50;
    display: flex;
    align-items: center;
    padding: 0 8px;
    gap: 3px;
  }
  #header select {
    padding: 4px 6px;
    border-radius: 4px;
    border: 1px solid #7f8c8d;
    background: #34495e;
    color: #ecf0f1;
    font-size: 12px;
    cursor: pointer;
    outline: none;
  }
  #header select:hover { background: #3d566e; }
  #header button {
    width: 30px;
    height: 30px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 16px;
    background: #34495e;
    color: #ecf0f1;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  #header button:hover { background: #3d566e; }
  #header button.active {
    background: #c0392b;
    box-shadow: inset 0 0 0 2px #e74c3c;
  }
  #header button.primary { background: #27ae60; }

  .search-wrap {
    position: relative;
    display: flex;
    align-items: center;
    gap: 2px;
  }
  .search-wrap input {
    width: 120px;
    padding: 4px 6px;
    border-radius: 4px;
    border: 1px solid #7f8c8d;
    background: #34495e;
    color: #ecf0f1;
    font-size: 12px;
    outline: none;
  }
  .search-wrap input::placeholder { color: #7f8c8d; }
  #searchResults {
    position: absolute;
    top: 100%;
    left: 0;
    width: 300px;
    max-height: 200px;
    overflow-y: auto;
    background: #34495e;
    border: 1px solid #7f8c8d;
    border-radius: 4px;
    z-index: 10000;
    display: none;
  }
  #searchResults div {
    padding: 6px 10px;
    color: #ecf0f1;
    font-size: 11px;
    cursor: pointer;
    border-bottom: 1px solid #2c3e50;
    line-height: 1.3;
  }
  #searchResults div:last-child { border-bottom: none; }
  #searchResults div:hover { background: #3d566e; }

  #status {
    margin-left: auto;
    color: #bdc3c7;
    font-size: 12px;
    white-space: nowrap;
    font-family: 'Segoe UI', sans-serif;
  }

  #map { width: 100%; height: calc(100% - 44px); }
  .leaflet-container { background: #1a1a2e; }
</style>
</head>
<body>
<div id="header">
  <select id="providerSelect">
    <option value="google">Google</option>
    <option value="yandex">Yandex</option>
  </select>
  <button id="drawBtn" title="Рисовать полигон">&#x1F58C;&#xFE0F;</button>
  <button id="clearBtn" title="Очистить всё">&#x1F5D1;&#xFE0F;</button>
  <button id="saveBtn" class="primary" title="Сохранить">&#x1F4BE;</button>
  <div class="search-wrap">
    <input id="searchInput" type="text" placeholder="Поиск..." />
    <button id="searchBtn" title="Поиск">&#x1F50D;</button>
    <div id="searchResults"></div>
  </div>
  <button id="zoomInBtn" title="Приблизить">&#x2795;</button>
  <button id="zoomOutBtn" title="Отдалить">&#x2796;</button>
  <button id="fitBtn" title="Показать все">&#x229F;</button>
  <span id="status">Беларусь</span>
</div>
<div id="map"></div>

<script>
""" + _TILE_PROVIDERS_JS + r"""

// ---- State ----
var currentProvider = 'google';
var tileLayer = null;
var map = null;
var drawLayer = L.featureGroup();
var zoomBeforeDraw = 7;

var isDrawing = false;
var tempPoints = [];
var previewPolygon = null;
var drawnPolygons = []; // { polygon: L.Polygon, markers: [L.Marker] }

// ---- Geodesic area (Earth authalic sphere) ----
function geodesicArea(latlngs) {
    if (!latlngs || latlngs.length < 3) return 0;
    var area = 0;
    var len = latlngs.length;
    for (var i = 0; i < len; i++) {
        var p1 = latlngs[i];
        var p2 = latlngs[(i + 1) % len];
        area += (p2.lng - p1.lng) * (2 + Math.sin(p1.lat * Math.PI / 180) + Math.sin(p2.lat * Math.PI / 180));
    }
    var R = 6378137;
    return Math.abs(area * R * R / 2 * Math.PI / 180);
}

// ---- Provider switching ----
function switchProvider() {
    var sel = document.getElementById('providerSelect');
    currentProvider = sel.value;
    var prov = tileProviders[currentProvider];
    if (!prov) return;
    if (tileLayer) { map.removeLayer(tileLayer); }
    tileLayer = L.tileLayer(prov.url, {
        maxZoom: prov.maxZoom,
        attribution: prov.attribution
    }).addTo(map);
}

// ---- Map init ----
map = L.map('map', {
    center: [53.9, 27.57],
    zoom: 7,
    zoomControl: false,
});
drawLayer.addTo(map);
switchProvider();

// ---- Drawing ----
function toggleDrawMode() {
    if (isDrawing) {
        cancelDrawing();
        document.getElementById('drawBtn').classList.remove('active');
    } else {
        startDrawing();
        document.getElementById('drawBtn').classList.add('active');
    }
}

function startDrawing() {
    isDrawing = true;
    tempPoints = [];
    previewPolygon = null;
    zoomBeforeDraw = map.getZoom();
    map.getContainer().style.cursor = 'crosshair';
    map.on('click', onDrawClick);
    map.on('contextmenu', onDrawRightClick);
    setStatus('Клик — вершина, правая кнопка — завершить');
}

function cancelDrawing() {
    if (previewPolygon && drawLayer.hasLayer(previewPolygon)) {
        drawLayer.removeLayer(previewPolygon);
    }
    previewPolygon = null;
    tempPoints = [];
    isDrawing = false;
    map.off('click', onDrawClick);
    map.off('contextmenu', onDrawRightClick);
    map.getContainer().style.cursor = '';
}

function onDrawClick(e) {
    // Check if clicking near first vertex to close polygon
    if (tempPoints.length >= 3) {
        var firstPt = L.latLng(tempPoints[0][0], tempPoints[0][1]);
        var firstContainer = map.latLngToContainerPoint(firstPt);
        var clickContainer = map.latLngToContainerPoint(e.latlng);
        var distPx = firstContainer.distanceTo(clickContainer);
        if (distPx < 15) {
            finishDrawing();
            return;
        }
    }

    tempPoints.push([e.latlng.lat, e.latlng.lng]);
    updatePreview();
}

function onDrawRightClick(e) {
    L.DomEvent.preventDefault(e.originalEvent);
    if (tempPoints.length >= 3) {
        finishDrawing();
    } else {
        setStatus('Минимум 3 точки для полигона');
    }
}

function updatePreview() {
    if (previewPolygon && drawLayer.hasLayer(previewPolygon)) {
        drawLayer.removeLayer(previewPolygon);
    }
    if (tempPoints.length >= 1) {
        previewPolygon = L.polygon(tempPoints, {
            color: '#e74c3c',
            weight: 2,
            fillColor: '#e74c3c',
            fillOpacity: 0.1,
            dashArray: '5, 8'
        }).addTo(drawLayer);
    }
}

function finishDrawing() {
    if (tempPoints.length < 3) {
        setStatus('Минимум 3 точки для полигона');
        return;
    }

    // Save points before cancelDrawing clears them
    var savedPoints = tempPoints.slice();

    // Clean up preview and input handlers
    cancelDrawing();

    // Create final polygon
    var polygon = L.polygon(savedPoints, {
        color: '#e74c3c',
        weight: 2,
        fillColor: '#e74c3c',
        fillOpacity: 0.15
    }).addTo(drawLayer);

    // Create draggable vertex markers
    var markerIcon = L.divIcon({
        className: 'vertex-marker',
        iconSize: [12, 12],
        iconAnchor: [6, 6]
    });

    var markers = savedPoints.map(function(pt) {
        var m = L.marker(pt, {
            draggable: true,
            icon: markerIcon
        }).addTo(drawLayer);
        return m;
    });

    // When any marker drags, update polygon
    var updateFn = function() { updatePolygonFromMarkers(polygon, markers); };
    markers.forEach(function(m) { m.on('drag', updateFn); });

    drawnPolygons.push({ polygon: polygon, markers: markers });

    document.getElementById('drawBtn').classList.remove('active');
    updateStatus();
}

function updatePolygonFromMarkers(polygon, markers) {
    var latlngs = markers.map(function(m) { return m.getLatLng(); });
    polygon.setLatLngs([latlngs]);
    updateStatus();
}

// ---- Clear ----
function onClear() {
    drawnPolygons.forEach(function(dp) {
        if (dp.polygon && drawLayer.hasLayer(dp.polygon)) drawLayer.removeLayer(dp.polygon);
        dp.markers.forEach(function(m) {
            if (drawLayer.hasLayer(m)) drawLayer.removeLayer(m);
        });
    });
    drawnPolygons = [];

    if (isDrawing) {
        cancelDrawing();
        document.getElementById('drawBtn').classList.remove('active');
    }
    if (previewPolygon && drawLayer.hasLayer(previewPolygon)) {
        drawLayer.removeLayer(previewPolygon);
    }
    previewPolygon = null;
    tempPoints = [];

    setStatus('Полигоны очищены');
}

// ---- Area and status ----
function getTotalArea() {
    var total = 0;
    drawnPolygons.forEach(function(dp) {
        var latlngs = dp.polygon.getLatLngs();
        if (latlngs.length > 0 && latlngs[0].length > 0) {
            total += geodesicArea(latlngs[0]);
        }
    });
    return total;
}

function getCombinedBounds() {
    if (drawnPolygons.length === 0) return null;
    var bounds = drawnPolygons[0].polygon.getBounds();
    for (var i = 1; i < drawnPolygons.length; i++) {
        bounds.extend(drawnPolygons[i].polygon.getBounds().getSouthWest());
        bounds.extend(drawnPolygons[i].polygon.getBounds().getNorthEast());
    }
    return bounds;
}

function getPolygonsCoords() {
    return drawnPolygons.map(function(dp) {
        var latlngs = dp.polygon.getLatLngs()[0];
        return latlngs.map(function(ll) { return [ll.lat, ll.lng]; });
    });
}

function updateStatus() {
    var area = getTotalArea();
    var count = drawnPolygons.length;
    var areaHa = (area / 10000).toFixed(2);
    var text = (count > 0) ? ('S = ' + areaHa + ' \u0433\u0430') : '';
    setStatus(text);
}

// ---- Finish ----
function onFinish() {
    // Cancel any in-progress drawing first
    if (isDrawing) {
        if (tempPoints.length >= 3) {
            finishDrawing();
        } else {
            cancelDrawing();
            document.getElementById('drawBtn').classList.remove('active');
        }
    }

    if (drawnPolygons.length === 0) {
        setStatus('\u041d\u0430\u0440\u0438\u0441\u0443\u0439\u0442\u0435 \u0445\u043e\u0442\u044f \u0431\u044b \u043e\u0434\u0438\u043d \u043f\u043e\u043b\u0438\u0433\u043e\u043d!');
        return;
    }

    var coords = getPolygonsCoords();
    var bounds = getCombinedBounds();
    var totalArea = getTotalArea();

    if (!bounds) {
        setStatus('\u041e\u0448\u0438\u0431\u043a\u0430 \u0432\u044b\u0447\u0438\u0441\u043b\u0435\u043d\u0438\u044f \u0433\u0440\u0430\u043d\u0438\u0446');
        return;
    }

    var result = JSON.stringify({
        action: 'finish',
        provider: currentProvider,
        polygons: coords,
        bbox: {
            min_lat: bounds.getSouthWest().lat,
            min_lon: bounds.getSouthWest().lng,
            max_lat: bounds.getNorthEast().lat,
            max_lon: bounds.getNorthEast().lng,
        },
        total_area_sqm: totalArea,
        zoom: zoomBeforeDraw,
    });
    try { document.title = 'MAP_RESULT:' + result; } catch(e) {}
}

// ---- Fit all ----
function onFit() {
    if (drawnPolygons.length > 0) {
        var bounds = getCombinedBounds();
        if (bounds) map.fitBounds(bounds, { padding: [20, 20] });
    } else if (isDrawing && tempPoints.length > 0) {
        var pts = tempPoints.map(function(p) { return L.latLng(p[0], p[1]); });
        if (pts.length > 0) map.fitBounds(pts);
    } else {
        map.setView([53.9, 27.57], 7);
    }
}

// ---- Search (Nominatim) ----
var lastSearchTime = 0;
function doSearch() {
    var input = document.getElementById('searchInput');
    var results = document.getElementById('searchResults');
    var query = input.value.trim();
    if (!query) { results.style.display = 'none'; return; }

    var now = Date.now();
    if (now - lastSearchTime < 1000) return;
    lastSearchTime = now;

    setStatus('\u041f\u043e\u0438\u0441\u043a...');

    var url = 'https://nominatim.openstreetmap.org/search?format=json&q='
        + encodeURIComponent(query) + '&limit=5';
    fetch(url, {
        headers: {
            'Accept-Language': 'ru',
            'User-Agent': 'IGI-MapTiles/1.0'
        }
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        results.innerHTML = '';
        if (!data || data.length === 0) {
            results.innerHTML = '<div>\u041d\u0438\u0447\u0435\u0433\u043e \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e</div>';
            results.style.display = 'block';
            setStatus('');
            return;
        }
        data.forEach(function(item) {
            var div = document.createElement('div');
            div.textContent = item.display_name;
            div.addEventListener('click', function() {
                var bbox = item.boundingbox;
                if (bbox) {
                    map.fitBounds([
                        [parseFloat(bbox[0]), parseFloat(bbox[2])],
                        [parseFloat(bbox[1]), parseFloat(bbox[3])]
                    ]);
                }
                results.style.display = 'none';
                setStatus('');
            });
            results.appendChild(div);
        });
        results.style.display = 'block';
        setStatus('');
    })
    .catch(function(err) {
        results.innerHTML = '<div>\u041e\u0448\u0438\u0431\u043a\u0430 \u043f\u043e\u0438\u0441\u043a\u0430</div>';
        results.style.display = 'block';
        setStatus('');
    });
}

// ---- CSS for vertex markers ----
var styleSheet = document.createElement('style');
styleSheet.textContent = '.vertex-marker { background: #e74c3c; border: 2px solid #fff; border-radius: 50%; }';
document.head.appendChild(styleSheet);

// ---- Wire up header buttons ----
document.getElementById('providerSelect').addEventListener('change', switchProvider);
document.getElementById('drawBtn').addEventListener('click', toggleDrawMode);
document.getElementById('clearBtn').addEventListener('click', onClear);
document.getElementById('saveBtn').addEventListener('click', onFinish);
document.getElementById('searchBtn').addEventListener('click', doSearch);
document.getElementById('searchInput').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') { doSearch(); }
});
document.getElementById('zoomInBtn').addEventListener('click', function() { map.zoomIn(); });
document.getElementById('zoomOutBtn').addEventListener('click', function() { map.zoomOut(); });
document.getElementById('fitBtn').addEventListener('click', onFit);

// Close search results when clicking outside
document.addEventListener('click', function(e) {
    if (!e.target.closest('.search-wrap')) {
        document.getElementById('searchResults').style.display = 'none';
    }
});

// ---- Download progress & cancel ----
function cancelDownload() {
    try { document.title = 'CANCEL_DOWNLOAD'; } catch(e) {}
    var btn = document.getElementById('cancelBtn');
    btn.disabled = true;
    btn.textContent = 'Отмена...';
    btn.style.background = '#7f8c8d';
}

function showProgress(current, total) {
    var container = document.getElementById('progressContainer');
    container.style.display = 'block';
    var pct = total > 0 ? Math.min(100, Math.round(current / total * 100)) : 0;
    document.getElementById('progressBar').style.width = pct + '%';
    document.getElementById('progressText').textContent = current + ' / ' + total + ' (' + pct + '%)';
}

function hideProgress() {
    document.getElementById('progressContainer').style.display = 'none';
}

// ---- Util ----
function setStatus(text) {
    document.getElementById('status').textContent = text;
}
</script>

<div id="progressContainer" style="display:none; position:absolute; bottom:20px; left:50%; transform:translateX(-50%); z-index:10000; background:rgba(0,0,0,0.85); color:white; padding:16px 24px; border-radius:8px; min-width:320px; text-align:center; font-family:'Segoe UI',sans-serif;">
  <div id="progressTitle" style="margin-bottom:8px; font-size:13px;">Загрузка тайлов...</div>
  <div style="width:100%; height:10px; background:#555; border-radius:5px; overflow:hidden;">
    <div id="progressBar" style="width:0%; height:100%; background:#27ae60; border-radius:5px; transition:width 0.3s;"></div>
  </div>
  <div id="progressText" style="font-size:11px; margin-top:5px; color:#aaa;">0 / 0 (0%)</div>
  <button id="cancelBtn" onclick="cancelDownload()" style="margin-top:10px; padding:5px 24px; background:#e74c3c; color:white; border:none; border-radius:4px; cursor:pointer; font-size:13px;">Отмена</button>
</div>

</body>
</html>"""


# ---------------------------------------------------------------------------
# wxWebView диалог
# ---------------------------------------------------------------------------

_MAP_RESULT_PREFIX = "MAP_RESULT:"


class MapDialog(wx.Dialog):
    """Модальный диалог с интерактивной картой для выбора полигона.

    После закрытия:
      - result_data: dict | None — результат с полигонами, провайдером или None
    """

    def __init__(
        self,
        parent: wx.Window | None = None,
        title: str = "IGI Map Tiles — карта",
        size: tuple[int, int] = (1000, 700),
    ):
        super().__init__(
            parent,
            title=title,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.STAY_ON_TOP,
        )
        self.SetMinSize(wx.Size(700, 500))
        self.SetSize(wx.Size(size[0], size[1]))

        self.result_data: dict | None = None
        self._pending_result: str | None = None
        self._cancel_download = False
        self._download_thread: threading.Thread | None = None
        self._download_result: dict | None = None

        self._poll_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_poll, self._poll_timer)

        self._create_ui()

        self.Bind(wx.EVT_CLOSE, self._on_close)

        self.CentreOnScreen()

    def _create_ui(self) -> None:
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.browser = wx.html2.WebView.New(self)
        self.browser.SetPage(_LEAFLET_HTML, "")

        sizer.Add(self.browser, proportion=1, flag=wx.EXPAND)
        self.SetSizer(sizer)

        self._poll_timer.Start(500)

    def _on_poll(self, event) -> None:
        """Опрашиваем заголовок страницы на наличие результата/команды отмены."""
        try:
            title = self.browser.GetCurrentTitle() or ""

            # Cancel download command from JS
            if title.startswith("CANCEL_DOWNLOAD"):
                self._cancel_download = True
                try:
                    self.browser.RunScript("document.title = 'cancelling';")
                except Exception:
                    pass
                return

            # Map result received — start background download
            if title.startswith(_MAP_RESULT_PREFIX) and not self._download_thread:
                json_str = title[len(_MAP_RESULT_PREFIX):]
                try:
                    data = json.loads(json_str)
                    self._start_download(data)
                except json.JSONDecodeError:
                    pass
                return

            # Download complete — close dialog with result
            if self._download_result:
                self.result_data = self._download_result
                self._download_result = None  # guarded: one shot only
                self._poll_timer.Stop()
                wx.CallAfter(self.EndModal, wx.ID_OK)

        except Exception:
            pass

    def _start_download(self, data: dict) -> None:
        """Запускает фоновую загрузку тайлов и показывает прогресс в HTML."""
        from .tile_downloader import (
            download_all_tiles,
            get_default_providers,
            get_tiles_in_bbox,
        )
        from .tile_stitcher import stitch_tiles

        provider_id = data.get("provider", "google")
        polygons = data.get("polygons", [])
        bbox = data.get("bbox", {})

        if not polygons or not bbox:
            self._download_result = None
            return

        self._cancel_download = False

        def _do_download() -> None:
            try:
                providers = get_default_providers()
                provider_match = next(
                    (p for p in providers if p.id == provider_id), None
                )
                if provider_match is None:
                    print(f"[MapTiles] Провайдер {provider_id} не найден")
                    wx.CallAfter(self._show_error, "Провайдер не найден")
                    return

                zoom = provider_match.max_zoom
                min_lon = bbox.get("min_lon")
                min_lat = bbox.get("min_lat")
                max_lon = bbox.get("max_lon")
                max_lat = bbox.get("max_lat")
                tile_coords = get_tiles_in_bbox(
                    min_lon, min_lat, max_lon, max_lat, zoom
                )
                total_tiles = len(tile_coords)

                if total_tiles == 0:
                    wx.CallAfter(self._show_error, "Нет тайлов для загрузки")
                    return

                cancel_event = threading.Event()

                def _progress(cur: int, total: int) -> None:
                    wx.CallAfter(self._update_progress_js, cur, total)
                    if self._cancel_download:
                        cancel_event.set()

                result = download_all_tiles(
                    tile_coords,
                    provider_match,
                    progress_callback=_progress,
                    max_concurrency=6,
                    cancel_event=cancel_event,
                )

                if self._cancel_download:
                    wx.CallAfter(self._on_download_cancelled)
                    return

                tile_data = result.get("data", {})
                if not tile_data:
                    wx.CallAfter(self._show_error, "Не удалось загрузить тайлы")
                    return

                wx.CallAfter(
                    self._update_progress_status, "Склейка тайлов..."
                )

                temp_dir = os.path.join(
                    os.environ.get("TEMP", "C:\\Temp"), "IGI_MapTiles"
                )
                os.makedirs(temp_dir, exist_ok=True)
                output_name = f"map_tiles_{int(time.time())}.png"
                output_path = os.path.normpath(
                    os.path.join(temp_dir, output_name)
                )

                tile_data_xy = {
                    (x, y): data
                    for (x, y, z), data in tile_data.items()
                }
                stitch_result = stitch_tiles(
                    tile_data_xy, tile_coords, output_path
                )

                if stitch_result["tiles_stitched"] == 0:
                    wx.CallAfter(self._show_error, "Не удалось склеить тайлы")
                    return

                from .tile_downloader import get_bbox_mercator_size

                merc_w, merc_h = get_bbox_mercator_size(
                    min_lon, min_lat, max_lon, max_lat,
                )

                result_data = {
                    "action": "finish",
                    "provider": provider_id,
                    "polygons": polygons,
                    "bbox": bbox,
                    "total_area_sqm": data.get("total_area_sqm", 0),
                    "png_path": stitch_result["path"],
                    "png_width": stitch_result["width"],
                    "png_height": stitch_result["height"],
                    "mercator_width": merc_w,
                    "mercator_height": merc_h,
                    "zoom": data.get("zoom", zoom),
                }

                wx.CallAfter(self._on_download_complete, result_data)

            except Exception:
                import traceback

                traceback.print_exc()
                wx.CallAfter(self._show_error, "Ошибка загрузки")

        try:
            self.browser.RunScript("showProgress(0, 1);")
        except Exception:
            pass

        self._download_thread = threading.Thread(
            target=_do_download, daemon=True
        )
        self._download_thread.start()

    def _update_progress_js(self, current: int, total: int) -> None:
        js = f"showProgress({current}, {total});"
        try:
            self.browser.RunScript(js)
        except Exception:
            pass

    def _update_progress_status(self, status: str) -> None:
        js = (
            "document.getElementById('progressTitle').textContent"
            f" = '{status}';"
        )
        try:
            self.browser.RunScript(js)
        except Exception:
            pass

    def _show_error(self, message: str) -> None:
        js = (
            "document.getElementById('progressTitle').textContent"
            f" = 'Ошибка: {message}';"
            "document.getElementById('progressTitle').style.color"
            " = '#e74c3c';"
            "document.getElementById('cancelBtn').style.display"
            " = 'none';"
            "setTimeout(function(){"
            "  document.title = 'MAP_ERROR';"
            "}, 2000);"
        )
        try:
            self.browser.RunScript(js)
        except Exception:
            pass
        wx.CallLater(3000, self._on_download_error)

    def _on_download_cancelled(self) -> None:
        js = (
            "document.getElementById('progressTitle').textContent"
            " = 'Загрузка отменена';"
            "document.getElementById('progressBar').style.background"
            " = '#f39c12';"
            "document.getElementById('cancelBtn').style.display"
            " = 'none';"
            "setTimeout(function(){"
            "  hideProgress();"
            "  document.title = 'MAP_CANCELLED';"
            "}, 1500);"
        )
        try:
            self.browser.RunScript(js)
        except Exception:
            pass
        self._cancel_download = False
        self._download_thread = None

    def _on_download_complete(self, result_data: dict) -> None:
        self._download_result = result_data
        js = (
            "document.getElementById('progressTitle').textContent"
            " = 'Загрузка завершена!';"
            "document.getElementById('progressTitle').style.color"
            " = '#27ae60';"
            "document.getElementById('progressBar').style.width"
            " = '100%';"
            "document.getElementById('progressBar').style.background"
            " = '#27ae60';"
            "document.getElementById('cancelBtn').style.display"
            " = 'none';"
        )
        try:
            self.browser.RunScript(js)
        except Exception:
            pass

    def _on_download_error(self) -> None:
        self._download_result = None
        self.EndModal(wx.ID_CANCEL)

    def _on_close(self, event) -> None:
        self._poll_timer.Stop()
        self._cancel_download = True
        self.result_data = self._download_result
        if self._download_result:
            self.EndModal(wx.ID_OK)
        else:
            self.EndModal(wx.ID_CANCEL)


# ---------------------------------------------------------------------------
# Функция для вызова диалога
# ---------------------------------------------------------------------------


def show_map_dialog() -> dict | None:
    """Показать диалог с картой. Вернуть данные полигонов/провайдера или None."""
    dlg = MapDialog()
    try:
        if dlg.ShowModal() == wx.ID_OK:
            return dlg.result_data
        return None
    except Exception as exc:
        traceback.print_exc()
        print(f"[IGI Map Tiles] Ошибка карты: {exc}")
        return None
    finally:
        dlg.Destroy()