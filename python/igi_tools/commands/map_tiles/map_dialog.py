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
# HTML-шаблон карты на Leaflet.js
# ---------------------------------------------------------------------------

_LEAFLET_HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="pragma" content="no-cache">
<meta http-equiv="cache-control" content="no-cache, no-store, must-revalidate">
<title>IGI Map Tiles</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 100%; height: 100%; overflow: hidden; }
  body { font-family: 'Segoe UI', sans-serif; }

  #map { width: 100%; height: 100%; position: absolute; top: 0; left: 0; }
  .leaflet-container {
    background: linear-gradient(135deg, #132238 0%, #1b3350 50%, #1f3a55 100%);
  }

  /* ---- Tool panel (top-right, blur + teal tint) ---- */
  #toolPanel {
    position: absolute;
    top: 12px;
    right: 12px;
    z-index: 1000;
    background: rgba(16,34,50,0.82);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid rgba(137,203,250,0.15);
    border-radius: 10px;
    padding: 6px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.5);
  }
  #toolPanel button {
    width: 36px;
    height: 36px;
    border: none;
    border-radius: 7px;
    cursor: pointer;
    background: rgba(255,255,255,0.06);
    color: #ecf0f1;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s, transform 0.15s;
  }
  #toolPanel button:hover { background: rgba(255,255,255,0.16); transform: scale(1.1); }
  #toolPanel button:active { transform: scale(0.92); }
  #toolPanel button.active {
    background: rgba(231,76,60,0.35);
    box-shadow: 0 0 8px rgba(231,76,60,0.25);
  }
  #toolPanel button.primary { color: #82D99F; }
  #toolPanel button.primary:hover { background: rgba(39,174,96,0.35); }
  #toolPanel .sep {
    width: 100%;
    height: 1px;
    background: rgba(255,255,255,0.07);
    margin: 2px 0;
  }

  /* ---- Search panel (top-left, semi-transparent) ---- */
  #searchPanel {
    position: absolute;
    top: 12px;
    left: 12px;
    z-index: 1000;
  }
  #searchPanel .search-wrap {
    position: relative;
    display: flex;
    align-items: center;
  }
  #searchPanel .search-wrap input {
    width: 320px;
    padding: 9px 14px 9px 34px;
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.1);
    background: rgba(0,0,0,0.55);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    color: #ecf0f1;
    font-size: 13px;
    outline: none;
    transition: border-color 0.2s, background 0.2s;
  }
  #searchPanel .search-wrap input:focus {
    border-color: rgba(52,152,219,0.4);
    background: rgba(0,0,0,0.7);
  }
  #searchPanel .search-wrap input::placeholder { color: #7f8c8d; }
  #searchPanel .search-wrap::before {
    content: '';
    position: absolute;
    left: 11px;
    top: 50%;
    transform: translateY(-50%);
    width: 14px;
    height: 14px;
    background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%237f8c8d'%3E%3Cpath d='M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z'/%3E%3C/svg%3E") no-repeat center;
    background-size: contain;
    pointer-events: none;
    z-index: 1;
  }
  #searchPanel .search-wrap.loading::before {
    background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%233498db'%3E%3Cpath d='M12 4V2A10 10 0 0 0 2 12h2a8 8 0 0 1 8-8z'/%3E%3C/svg%3E") no-repeat center;
    background-size: contain;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { from { transform: translateY(-50%) rotate(0deg); } to { transform: translateY(-50%) rotate(360deg); } }

  #searchResults {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    width: 360px;
    max-height: 240px;
    overflow-y: auto;
    background: rgba(37,53,68,0.95);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    z-index: 10000;
    display: none;
    padding: 4px 0;
  }
  #searchResults .sr-item {
    padding: 8px 12px;
    color: #ecf0f1;
    font-size: 12px;
    cursor: pointer;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    line-height: 1.4;
    transition: background 0.12s;
  }
  #searchResults .sr-item:last-child { border-bottom: none; }
  #searchResults .sr-item:hover { background: rgba(52,152,219,0.25); }
  #searchResults .sr-item .sr-label {
    font-weight: 600;
    color: #3498db;
    font-size: 11px;
  }
  #searchResults .sr-empty {
    padding: 12px;
    color: #95a5a6;
    font-size: 12px;
    text-align: center;
    font-style: italic;
  }
  #searchResults .sr-error {
    padding: 12px;
    color: #e67e22;
    font-size: 12px;
    text-align: center;
  }

  /* ---- Bottom-left status ---- */
  #status {
    position: absolute;
    bottom: 12px;
    left: 12px;
    z-index: 1000;
    color: rgba(189,195,199,0.85);
    font-size: 12px;
    font-family: 'Segoe UI', sans-serif;
    background: rgba(0,0,0,0.45);
    padding: 4px 10px;
    border-radius: 5px;
    pointer-events: none;
  }
</style>
</head>
<body>
<div id="searchPanel">
  <div class="search-wrap">
    <input id="searchInput" type="text" placeholder="Поиск места..." autocomplete="off" spellcheck="false" />
    <div id="searchResults"></div>
  </div>
</div>

<div id="toolPanel">
  <!-- Navigation -->
  <button id="fitBtn" title="Показать все"><svg viewBox="0 0 32 32" width="20" height="20"><path d="M 5,5 L 11,5 L 11,7 L 7,7 L 7,11 L 5,11 Z" fill="currentColor"/><path d="M 21,5 L 27,5 L 27,11 L 25,11 L 25,7 L 21,7 Z" fill="currentColor"/><path d="M 5,21 L 7,21 L 7,25 L 11,25 L 11,27 L 5,27 Z" fill="currentColor"/><path d="M 21,27 L 27,27 L 27,21 L 25,21 L 25,25 L 21,25 Z" fill="currentColor"/></svg></button>
  <div class="sep"></div>
  <!-- Tile zoom level selector -->
<button id="zoomDownBtn" title="Уменьшить зум (−1)"><svg viewBox="0 0 32 32" width="20" height="20"><circle cx="14" cy="14" r="9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M 21,21 L 28,28" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/><path d="M 10,14 L 18,14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button>
  <span id="zoomValue" style="font-size:14px;font-weight:bold;color:#ecf0f1;width:36px;text-align:center;line-height:36px;cursor:default;" title="Текущий зум карты и тайлов">7</span>
<button id="zoomUpBtn" title="Увеличить зум (+1)"><svg viewBox="0 0 32 32" width="20" height="20"><circle cx="14" cy="14" r="9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M 21,21 L 28,28" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/><path d="M 10,14 L 18,14 M 14,10 L 14,18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button>
  <div class="sep"></div>
  <!-- Drawing tools (bottom group) -->
  <button id="drawBtn" title="Прямоугольная область"><svg viewBox="0 0 32 32" width="20" height="20"><rect x="4" y="4" width="24" height="24" rx="1.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M 4,4 L 28,28" fill="none" stroke="currentColor" stroke-width="1.5" stroke-dasharray="3,3" stroke-linecap="round"/></svg></button>
  <button id="clearBtn" title="Очистить всё"><svg viewBox="0 0 32 32" width="20" height="20"><path d="M 6,4 L 4,6 L 14,16 L 4,26 L 6,28 L 16,18 L 26,28 L 28,26 L 18,16 L 28,6 L 26,4 L 16,14 Z" fill="currentColor"/></svg></button>
  <div class="sep"></div>
  <button id="saveBtn" class="primary" title="Скачать тайлы"><svg viewBox="0 0 32 32" width="20" height="20"><rect x="6" y="6" width="20" height="20" rx="1.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><rect x="10" y="22" width="12" height="4" rx="0.5" fill="currentColor"/><path d="M 16,6 L 16,16 M 12,12 L 16,16 L 20,12" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
</div>

<div id="status"></div>
<div id="map"></div>

<script>

// ---- State ----
var tileLayer = null;
var map = null;
var drawLayer = L.featureGroup();
var zoomBeforeDraw = 7;
var tileZoom = 7;   // синхронизируется с zoom карты после инициализации

var isDrawing = false;
var rectangle = null;          // L.Rectangle
var cornerMarkers = [];        // [L.Marker] — 4 угла
var cornerPoints = null;       // { nw, ne, se, sw }
var firstCornerPt = null;
var previewRect = null;

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

// ---- Map init ----
map = L.map('map', {
    center: [53.9, 27.57],
    zoom: 7,
    zoomControl: false,
});
drawLayer.addTo(map);
tileLayer = L.tileLayer('https://mt.google.com/vt/lyrs=y&x={x}&y={y}&z={z}&hl=ru_RU', {
    maxZoom: 20,
    attribution: '\u00a9 Google',
    tms: false
}).addTo(map);

// ---- Синхронизация zoom карты и zoom тайлов ----
tileZoom = map.getZoom();
document.getElementById('zoomValue').textContent = tileZoom;
map.on('zoomend', function() {
    tileZoom = map.getZoom();
    document.getElementById('zoomValue').textContent = tileZoom;
});

// ---- Drawing ----
var _dragAnchor = null; // противоположный угол при перетаскивании
var CORNER_KEYS = ['nw', 'ne', 'se', 'sw'];

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
    firstCornerPt = null;
    previewRect = null;
    zoomBeforeDraw = map.getZoom();
    map.getContainer().style.cursor = 'crosshair';
    map.on('click', onRectClick);
    map.on('mousemove', onRectMove);
    map.on('contextmenu', onRectRightClick);
    setStatus('Клик — первый угол, второй клик — противоположный угол');
}

function cancelDrawing() {
    if (previewRect && drawLayer.hasLayer(previewRect)) {
        drawLayer.removeLayer(previewRect);
    }
    previewRect = null;
    firstCornerPt = null;
    isDrawing = false;
    map.off('click', onRectClick);
    map.off('mousemove', onRectMove);
    map.off('contextmenu', onRectRightClick);
    map.getContainer().style.cursor = '';
}

function onRectClick(e) {
    if (firstCornerPt === null) {
        firstCornerPt = e.latlng;
    } else {
        finishRectangle(firstCornerPt, e.latlng);
    }
}

function onRectRightClick(e) {
    L.DomEvent.preventDefault(e.originalEvent);
    if (firstCornerPt !== null) {
        finishRectangle(firstCornerPt, e.latlng);
    } else {
        setStatus('Кликните первый угол');
    }
}

function onRectMove(e) {
    if (firstCornerPt === null) return;
    if (previewRect && drawLayer.hasLayer(previewRect)) {
        drawLayer.removeLayer(previewRect);
    }
    previewRect = L.rectangle([firstCornerPt, e.latlng], {
        color: '#e74c3c',
        weight: 2,
        fillColor: '#e74c3c',
        fillOpacity: 0.1,
        dashArray: '5, 8'
    }).addTo(drawLayer);
}

function finishRectangle(corner1, corner2) {
    cancelDrawing();

    var minLat = Math.min(corner1.lat, corner2.lat);
    var maxLat = Math.max(corner1.lat, corner2.lat);
    var minLng = Math.min(corner1.lng, corner2.lng);
    var maxLng = Math.max(corner1.lng, corner2.lng);

    cornerPoints = {
        nw: L.latLng(maxLat, minLng),
        ne: L.latLng(maxLat, maxLng),
        se: L.latLng(minLat, maxLng),
        sw: L.latLng(minLat, minLng)
    };

    rectangle = L.rectangle([cornerPoints.se, cornerPoints.nw], {
        color: '#e74c3c',
        weight: 2,
        fillColor: '#e74c3c',
        fillOpacity: 0.15
    }).addTo(drawLayer);

    createCornerMarkers();
    document.getElementById('drawBtn').classList.remove('active');
    updateStatus();
}

function createCornerMarkers() {
    clearCornerMarkers();
    CORNER_KEYS.forEach(function(key) {
        var m = L.marker(cornerPoints[key], {
            draggable: true,
            icon: L.divIcon({
                className: 'corner-marker',
                iconSize: [12, 12],
                iconAnchor: [6, 6]
            })
        }).addTo(drawLayer);
        m._cornerKey = key;
        m.on('drag', onCornerDrag);
        m.on('dragstart', onCornerDragStart);
        cornerMarkers.push(m);
    });
}

function clearCornerMarkers() {
    cornerMarkers.forEach(function(m) {
        if (drawLayer.hasLayer(m)) drawLayer.removeLayer(m);
    });
    cornerMarkers = [];
}

var _OPPOSITE = { nw: 'se', ne: 'sw', se: 'nw', sw: 'ne' };

function onCornerDragStart(e) {
    var key = e.target._cornerKey;
    _dragAnchor = cornerPoints[_OPPOSITE[key]];
}

function onCornerDrag(e) {
    var marker = e.target;
    var moved = marker.getLatLng();
    var anchor = _dragAnchor;

    var minLat = Math.min(anchor.lat, moved.lat);
    var maxLat = Math.max(anchor.lat, moved.lat);
    var minLng = Math.min(anchor.lng, moved.lng);
    var maxLng = Math.max(anchor.lng, moved.lng);

    cornerPoints.nw = L.latLng(maxLat, minLng);
    cornerPoints.ne = L.latLng(maxLat, maxLng);
    cornerPoints.se = L.latLng(minLat, maxLng);
    cornerPoints.sw = L.latLng(minLat, minLng);

    rectangle.setBounds([cornerPoints.se, cornerPoints.nw]);

    cornerMarkers.forEach(function(m) {
        if (m !== marker) {
            m.setLatLng(cornerPoints[m._cornerKey]);
        }
    });

    updateStatus();
}

// ---- Clear ----
function onClear() {
    if (rectangle && drawLayer.hasLayer(rectangle)) {
        drawLayer.removeLayer(rectangle);
    }
    rectangle = null;
    clearCornerMarkers();
    cornerPoints = null;

    if (isDrawing) {
        cancelDrawing();
        document.getElementById('drawBtn').classList.remove('active');
    }
    if (previewRect && drawLayer.hasLayer(previewRect)) {
        drawLayer.removeLayer(previewRect);
    }
    previewRect = null;
    firstCornerPt = null;

    setStatus('Очищено');
}

// ---- Area and status ----
function getTotalArea() {
    if (!rectangle) return 0;
    var latlngs = [
        cornerPoints.nw,
        cornerPoints.ne,
        cornerPoints.se,
        cornerPoints.sw
    ];
    return geodesicArea(latlngs);
}

function getBounds() {
    if (!rectangle) return null;
    return rectangle.getBounds();
}

function getRectCoords() {
    if (!cornerPoints) return [];
    return [[
        [cornerPoints.nw.lat, cornerPoints.nw.lng],
        [cornerPoints.ne.lat, cornerPoints.ne.lng],
        [cornerPoints.se.lat, cornerPoints.se.lng],
        [cornerPoints.sw.lat, cornerPoints.sw.lng]
    ]];
}

function updateStatus() {
    var area = getTotalArea();
    var areaHa = (area / 10000).toFixed(2);
    var text = area > 0 ? ('S = ' + areaHa + ' \u0433\u0430') : '';
    setStatus(text);
}

// ---- Finish ----
function onFinish() {
    // Cancel any in-progress drawing first
    if (isDrawing) {
        cancelDrawing();
        document.getElementById('drawBtn').classList.remove('active');
    }

    if (!rectangle) {
        setStatus('\u041d\u0430\u0440\u0438\u0441\u0443\u0439\u0442\u0435 \u043f\u0440\u044f\u043c\u043e\u0443\u0433\u043e\u043b\u044c\u043d\u0438\u043a!');
        return;
    }

    var coords = getRectCoords();
    var bounds = getBounds();
    var totalArea = getTotalArea();

    if (!bounds) {
        setStatus('\u041e\u0448\u0438\u0431\u043a\u0430 \u0432\u044b\u0447\u0438\u0441\u043b\u0435\u043d\u0438\u044f \u0433\u0440\u0430\u043d\u0438\u0446');
        return;
    }

    var result = JSON.stringify({
        action: 'finish',
        provider: 'google',
        polygons: coords,
        bbox: {
            min_lat: bounds.getSouthWest().lat,
            min_lon: bounds.getSouthWest().lng,
            max_lat: bounds.getNorthEast().lat,
            max_lon: bounds.getNorthEast().lng,
        },
        total_area_sqm: totalArea,
        zoom: tileZoom,
    });
    try { document.title = 'MAP_RESULT:' + result; } catch(e) {}
}

// ---- Fit all ----
function onFit() {
    if (rectangle) {
        map.fitBounds(rectangle.getBounds(), { padding: [20, 20] });
    } else if (isDrawing && firstCornerPt) {
        map.fitBounds([firstCornerPt]);
    } else {
        map.setView([53.9, 27.57], 7);
    }
}

// ---- Real-time search (Nominatim) ----
var _searchDebounceTimer = null;
var _searchThrottleLast = 0;

function doSearch() {
    var input = document.getElementById('searchInput');
    var results = document.getElementById('searchResults');
    var query = input.value.trim();

    if (!query) {
        results.style.display = 'none';
        document.querySelector('.search-wrap').classList.remove('loading');
        return;
    }

    // Throttle: max 1 request/1.2s to Nominatim
    var now = Date.now();
    if (now - _searchThrottleLast < 1200) return;
    _searchThrottleLast = now;

    document.querySelector('.search-wrap').classList.add('loading');
    setStatus('\u041f\u043e\u0438\u0441\u043a...');

    var url = 'https://nominatim.openstreetmap.org/search?format=json&q='
        + encodeURIComponent(query) + '&limit=7';
    fetch(url, {
        headers: {
            'Accept-Language': 'ru',
            'User-Agent': 'IGI-MapTiles/1.0'
        }
    })
    .then(function(r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
    })
    .then(function(data) {
        document.querySelector('.search-wrap').classList.remove('loading');
        results.innerHTML = '';
        if (!data || data.length === 0) {
            results.innerHTML = '<div class="sr-empty">\u041d\u0438\u0447\u0435\u0433\u043e \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e.<br>\u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0443\u0442\u043e\u0447\u043d\u0438\u0442\u044c \u0437\u0430\u043f\u0440\u043e\u0441.</div>';
            results.style.display = 'block';
            setStatus('');
            return;
        }
        data.forEach(function(item) {
            var div = document.createElement('div');
            div.className = 'sr-item';
            // Show type badge + display name
            var type = item.type || '';
            var label = '';
            if (type) {
                var labels = {city:'\u0433\u043e\u0440\u043e\u0434', town:'\u043f\u043e\u0441\u0451\u043b\u043e\u043a', village:'\u0434\u0435\u0440\u0435\u0432\u043d\u044f',
                    hamlet:'\u0445\u0443\u0442\u043e\u0440', road:'\u0443\u043b\u0438\u0446\u0430', river:'\u0440\u0435\u043a\u0430', lake:'\u043e\u0437\u0435\u0440\u043e',
                    forest:'\u043b\u0435\u0441', country:'\u0441\u0442\u0440\u0430\u043d\u0430', state:'\u043e\u0431\u043b\u0430\u0441\u0442\u044c'};
                label = labels[type] || type;
            }
            var html = label ? '<span class="sr-label">' + label + '</span> ' : '';
            html += item.display_name;
            div.innerHTML = html;
            div.addEventListener('click', function() {
                var bbox = item.boundingbox;
                if (bbox) {
                    map.fitBounds([
                        [parseFloat(bbox[0]), parseFloat(bbox[2])],
                        [parseFloat(bbox[1]), parseFloat(bbox[3])]
                    ]);
                }
                results.style.display = 'none';
                document.getElementById('searchInput').value = item.display_name.split(',')[0];
                setStatus('');
            });
            results.appendChild(div);
        });
        results.style.display = 'block';
        setStatus('');
    })
    .catch(function(err) {
        document.querySelector('.search-wrap').classList.remove('loading');
        results.innerHTML = '';
        // Even on error, show a helpful message suggesting alternatives
        var suggestionEl = document.createElement('div');
        suggestionEl.className = 'sr-error';
        suggestionEl.innerHTML = '\u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 \u0438\u043b\u0438 \u043f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0434\u0440\u0443\u0433\u043e\u0439 \u0437\u0430\u043f\u0440\u043e\u0441';
        results.appendChild(suggestionEl);
        results.style.display = 'block';
        setStatus('');
    });
}

// ---- Debounced search trigger for real-time input ----
function onSearchInput() {
    if (_searchDebounceTimer) clearTimeout(_searchDebounceTimer);
    _searchDebounceTimer = setTimeout(doSearch, 350);
}

// ---- CSS for corner markers ----
var styleSheet = document.createElement('style');
styleSheet.textContent = '.corner-marker { background: #e74c3c; border: 2px solid #fff; border-radius: 50%; }';
document.head.appendChild(styleSheet);

// ---- Wire up header buttons ----
document.getElementById('drawBtn').addEventListener('click', toggleDrawMode);
document.getElementById('clearBtn').addEventListener('click', onClear);
document.getElementById('saveBtn').addEventListener('click', onFinish);
document.getElementById('searchInput').addEventListener('input', onSearchInput);
document.getElementById('searchInput').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
        if (_searchDebounceTimer) clearTimeout(_searchDebounceTimer);
        doSearch();
    }
});
document.getElementById('fitBtn').addEventListener('click', onFit);

// ---- Tile zoom controls ----
document.getElementById('zoomUpBtn').addEventListener('click', function() {
    map.setZoom(map.getZoom() + 1);
});
document.getElementById('zoomDownBtn').addEventListener('click', function() {
    map.setZoom(map.getZoom() - 1);
});



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
            get_bbox_mercator_size,
            get_default_providers,
            get_tile_grid_bbox,
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

                zoom = min(data.get("zoom", provider_match.max_zoom), provider_match.max_zoom)
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

                grid_bbox = get_tile_grid_bbox(tile_coords)
                print(f"[MapTiles][DEBUG] tile_coords count: {len(tile_coords)}")
                xs = [t[0] for t in tile_coords]
                ys = [t[1] for t in tile_coords]
                print(f"[MapTiles][DEBUG] tile grid: x=[{min(xs)},{max(xs)}], y=[{min(ys)},{max(ys)}], zoom={tile_coords[0][2]}")
                print(f"[MapTiles][DEBUG] grid_bbox: {grid_bbox}")
                merc_w, merc_h = get_bbox_mercator_size(*grid_bbox)
                print(f"[MapTiles][DEBUG] mercator_width={merc_w:.2f} м, mercator_height={merc_h:.2f} м")

                # Сохраняем метаданные JSON рядом с PNG
                meta_path = stitch_result["path"] + ".meta.json" if stitch_result.get("path") else None
                if meta_path:
                    try:
                        with open(meta_path, "w", encoding="utf-8") as mf:
                            json.dump({
                                "mercator_width_m": round(merc_w, 2),
                                "mercator_height_m": round(merc_h, 2),
                                "png_width_px": stitch_result["width"],
                                "png_height_px": stitch_result["height"],
                                "meters_per_pixel_x": round(merc_w / stitch_result["width"], 6),
                                "meters_per_pixel_y": round(merc_h / stitch_result["height"], 6),
                                "grid_lon_lat": list(grid_bbox),
                                "zoom": zoom,
                            }, mf, ensure_ascii=False, indent=2)
                    except Exception:
                        pass

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
                    "grid_bbox": list(grid_bbox),
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