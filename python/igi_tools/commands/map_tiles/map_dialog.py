"""wx-диалог с интерактивной картой для выбора полигона.

Использует wx.html2.WebView с Leaflet.js для отображения карты
и рисования полигона пользователем. Переключение провайдеров — внутри окна.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

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
        "attribution": "© Google"
    },
    "yandex": {
        "name": "Yandex",
        "url": "https://core-renderer-tiles.maps.yandex.net/tiles?l=sat&x={x}&y={y}&z={z}&lang=ru_RU",
        "maxZoom": 19,
        "attribution": "© Яндекс Карты"
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
<title>Выбор полигона на карте</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 100%; height: 100%; overflow: hidden; }
  #header {
    height: 44px;
    background: #2c3e50;
    display: flex;
    align-items: center;
    padding: 0 12px;
    gap: 6px;
  }
  #header select {
    padding: 4px 8px;
    border-radius: 4px;
    border: 1px solid #7f8c8d;
    background: #34495e;
    color: #ecf0f1;
    font-size: 13px;
    font-family: 'Segoe UI', sans-serif;
    cursor: pointer;
  }
  #header select:hover { background: #3d566e; }
  #header button {
    padding: 4px 12px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    font-family: 'Segoe UI', sans-serif;
  }
  #header button:hover { opacity: 0.85; }
  .btn-primary { background: #27ae60; color: #fff; }
  .btn-danger { background: #e74c3c; color: #fff; }
  .btn-warning { background: #f39c12; color: #fff; }
  .btn-info { background: #3498db; color: #fff; padding: 4px 10px !important; }
  #status {
    margin-left: auto;
    color: #bdc3c7;
    font-family: 'Segoe UI', sans-serif;
    font-size: 12px;
  }
  #coords_info {
    font-family: monospace;
    font-size: 11px;
    color: #7f8c8d;
    margin-left: 8px;
  }
  #map { width: 100%; height: calc(100% - 44px); }
  .leaflet-container { background: #1a1a2e; }
  #loading {
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    z-index: 10000;
    background: rgba(0,0,0,0.7);
    color: #fff;
    padding: 16px 32px;
    border-radius: 8px;
    font-family: 'Segoe UI', sans-serif;
    font-size: 14px;
  }
</style>
</head>
<body>
<div id="header">
  <select id="providerSelect" onchange="switchProvider()">
    <option value="google">Google</option>
    <option value="yandex">Yandex</option>
  </select>
  <button class="btn-primary" onclick="onFinish()">Готово</button>
  <button class="btn-warning" onclick="onDrawPolygon()">Полигон</button>
  <button class="btn-danger" onclick="onClear()">Очистить</button>
  <button class="btn-info" onclick="map.zoomIn()">+</button>
  <button class="btn-info" onclick="map.zoomOut()">-</button>
  <span id="status"></span>
  <span id="coords_info"></span>
</div>
<div id="map"></div>

<script>
""" + _TILE_PROVIDERS_JS + r"""

// ---- Провайдер тайлов ----
var currentProvider = 'google';
var tileLayer = null;

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

// ---- Инициализация карты ----
var map = L.map('map', {
    center: [55.75, 37.62],
    zoom: 12,
    zoomControl: false,
});

// Загружаем начальный слой (Google)
switchProvider();

// ---- Рисование полигона ----
var drawnPolygon = null;
var drawLayer = L.featureGroup().addTo(map);

var isDrawing = false;
var tempPoints = [];
var tempMarkers = [];

function onDrawPolygon() {
    if (isDrawing) { cancelDrawing(); return; }
    startDrawing();
}

function startDrawing() {
    isDrawing = true;
    tempPoints = [];
    tempMarkers = [];
    setStatus('Рисование: клик — вершина, двойной клик — завершить');
    map.on('click', onDrawClick);
    map.on('dblclick', onDrawDblClick);
}

function cancelDrawing() {
    isDrawing = false;
    map.off('click', onDrawClick);
    map.off('dblclick', onDrawDblClick);
    tempMarkers.forEach(function(m) { drawLayer.removeLayer(m); });
    tempMarkers = [];
    tempPoints = [];
    setStatus('Рисование отменено');
}

function onDrawClick(e) {
    tempPoints.push([e.latlng.lat, e.latlng.lng]);
    var marker = L.circleMarker(e.latlng, {
        radius: 5, color: '#e74c3c', fillColor: '#e74c3c', fillOpacity: 1
    }).addTo(drawLayer);
    tempMarkers.push(marker);
}

function onDrawDblClick(e) {
    finishDrawing();
}

function finishDrawing() {
    if (tempPoints.length < 3) {
        setStatus('Минимум 3 точки для полигона');
        return;
    }
    isDrawing = false;
    map.off('click', onDrawClick);
    map.off('dblclick', onDrawDblClick);
    // Удаляем временные маркеры
    tempMarkers.forEach(function(m) { drawLayer.removeLayer(m); });
    tempMarkers = [];
    // Создаём полигон
    drawnPolygon = L.polygon(tempPoints, {
        color: '#e74c3c', weight: 2, fillColor: '#e74c3c', fillOpacity: 0.15
    }).addTo(drawLayer);
    tempPoints = [];
    var area = L.GeometryUtil ? L.GeometryUtil.geodesicArea(drawnPolygon.getLatLngs()[0]) : 0;
    var coords = getPolygonCoords();
    var bounds = drawnPolygon.getBounds();
    map.fitBounds(bounds);
    setStatus(
        coords.length + ' вершин, S=' + (area/1000000).toFixed(3) + ' km²' +
        ' | SW: ' + bounds.getSouthWest().lat.toFixed(4) + ',' +
        bounds.getSouthWest().lng.toFixed(4) +
        ' NE: ' + bounds.getNorthEast().lat.toFixed(4) + ',' +
        bounds.getNorthEast().lng.toFixed(4)
    );
}

function getPolygonCoords() {
    if (!drawnPolygon) return [];
    var latlngs = drawnPolygon.getLatLngs()[0];
    return latlngs.map(function(ll) { return [ll.lat, ll.lng]; });
}

function onClear() {
    drawLayer.clearLayers();
    drawnPolygon = null;
    isDrawing = false;
    map.off('click', onDrawClick);
    map.off('dblclick', onDrawDblClick);
    tempPoints = [];
    tempMarkers = [];
    setStatus('Полигон очищен');
}

function setStatus(text) {
    document.getElementById('status').textContent = text;
}

function onFinish() {
    if (!drawnPolygon) {
        setStatus('Сначала нарисуйте полигон!');
        return;
    }
    var coords = getPolygonCoords();
    var bounds = drawnPolygon.getBounds();
    var zoom = map.getZoom();
    var result = JSON.stringify({
        action: 'finish',
        provider: currentProvider,
        polygon: coords,
        bbox: {
            min_lat: bounds.getSouthWest().lat,
            min_lon: bounds.getSouthWest().lng,
            max_lat: bounds.getNorthEast().lat,
            max_lon: bounds.getNorthEast().lng,
        },
        zoom: zoom,
    });
    try { document.title = 'MAP_RESULT:' + result; } catch(e) {}
}

function onFit() {
    if (drawnPolygon) { map.fitBounds(drawnPolygon.getBounds()); }
}

// Убираем загрузку
document.getElementById('loading').style.display = 'none';
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# wxWebView диалог
# ---------------------------------------------------------------------------

_MAP_RESULT_PREFIX = "MAP_RESULT:"


class MapDialog(wx.Dialog):
    """Модальный диалог с интерактивной картой для выбора полигона.

    После закрытия:
      - result_data: dict | None — результат с полигоном, провайдером или None
    """

    def __init__(
        self,
        parent: wx.Window | None = None,
        title: str = "IGI Map Tiles — Выбор полигона на карте",
        size: tuple[int, int] = (950, 680),
    ):
        super().__init__(
            parent,
            title=title,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.STAY_ON_TOP,
        )
        self.SetMinSize(wx.Size(680, 480))
        self.SetSize(wx.Size(size[0], size[1]))

        self.result_data: dict | None = None
        self._pending_result: str | None = None

        # Таймер — обязательно до _create_ui, где он запускается
        self._poll_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_poll, self._poll_timer)

        self._create_ui()

        self.Bind(wx.EVT_CLOSE, self._on_close)

        self.CentreOnScreen()

    def _create_ui(self) -> None:
        vbox = wx.BoxSizer(wx.VERTICAL)

        # WebView с картой
        self.browser = wx.html2.WebView.New(self)
        self.browser.SetPage(_LEAFLET_HTML, "")
        vbox.Add(self.browser, proportion=1, flag=wx.EXPAND)

        # Нижняя панель с кнопками
        btn_panel = wx.Panel(self)
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        provider_label = wx.StaticText(
            btn_panel, label="Провайдер: "
        )
        self.provider_choice = wx.Choice(
            btn_panel,
            choices=[
                "Google",
                "Yandex",
            ],
        )
        self.provider_choice.SetSelection(0)

        self.provider_choice.Bind(wx.EVT_CHOICE, self._on_provider_change)

        ok_btn = wx.Button(btn_panel, wx.ID_OK, "Принять полигон")
        cancel_btn = wx.Button(btn_panel, wx.ID_CANCEL, "Отмена")

        hbox.Add(provider_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=4)
        hbox.Add(self.provider_choice, flag=wx.RIGHT, border=16)
        hbox.Add(ok_btn, flag=wx.RIGHT, border=8)
        hbox.Add(cancel_btn)
        btn_panel.SetSizer(hbox)

        vbox.Add(btn_panel, flag=wx.ALIGN_LEFT | wx.ALL, border=8)

        self.SetSizer(vbox)

        # Bind
        self.Bind(wx.EVT_BUTTON, self._on_ok, ok_btn)
        self.Bind(wx.EVT_BUTTON, self._on_cancel, cancel_btn)

        # Запускаем опрос заголовка
        self._poll_timer.Start(500)

    def _on_provider_change(self, event) -> None:
        """Синхронизирует выбор провайдера в wx с JavaScript."""
        providers = ["google", "yandex"]
        idx = self.provider_choice.GetSelection()
        if 0 <= idx < len(providers):
            js = (
                f"document.getElementById('providerSelect').value = "
                f"'{providers[idx]}'; switchProvider();"
            )
            try:
                self.browser.RunScript(js)
            except Exception:
                pass

    def _on_poll(self, event) -> None:
        """Опрашиваем заголовок страницы на наличие результата."""
        try:
            title = self.browser.GetCurrentTitle() or ""
            if title.startswith(_MAP_RESULT_PREFIX):
                json_str = title[len(_MAP_RESULT_PREFIX):]
                self._pending_result = json_str
                self._poll_timer.Stop()
        except Exception:
            pass

    def _on_ok(self, event) -> None:
        if self._pending_result:
            try:
                data = json.loads(self._pending_result)
                self.result_data = data
            except json.JSONDecodeError:
                print("[IGI Map Tiles] Ошибка парсинга результата карты")
                self.result_data = None
        else:
            print("[IGI Map Tiles] Нажмите 'Готово' на карте сначала")
            return
        self.EndModal(wx.ID_OK)

    def _on_cancel(self, event) -> None:
        self.result_data = None
        self.EndModal(wx.ID_CANCEL)

    def _on_close(self, event) -> None:
        self._poll_timer.Stop()
        self.result_data = None
        self.EndModal(wx.ID_CANCEL)


# ---------------------------------------------------------------------------
# Функция для вызова диалога
# ---------------------------------------------------------------------------

def show_map_dialog() -> dict | None:
    """Показать диалог с картой. Вернуть данные полигона/провайдера или None."""
    from pyrx import Ap
    res_override = Ap.ResourceOverride()
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
        del res_override