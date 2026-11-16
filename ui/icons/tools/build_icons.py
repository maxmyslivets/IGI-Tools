#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IGI Tools — генератор единого набора иконок.

Стиль: Flat 2.0 по спецификации ui/icons/README.md репозитория IGI-Tools.
Сетка 32x32, прозрачный фон, двухслойная композиция (база + модификатор).

Все иконки строятся из общих примитивов, поэтому геометрия, толщины линий
и радиусы скруглений гарантированно одинаковы во всём наборе.

Запуск:  python3 tools/build_icons.py
"""

from __future__ import annotations

import json
import math
import os
import re

# ---------------------------------------------------------------------------
# ТОКЕНЫ ДИЗАЙН-СИСТЕМЫ
# ---------------------------------------------------------------------------

BASE = "#D9D9D9"   # Основной: базовый объект
ACC = "#89CBFA"    # Основной: главный акцент (действие / результат)
NEU = "#808080"    # Вспомогательный: нейтральный (источник / неактивное)
OUT = "#666666"    # Вспомогательный: контур / граница
PRC = "#82D99F"    # Вспомогательный: процессы / включение
MOD = "#FFD580"    # Вспомогательный: модификатор / правка
STA = "#FF6666"    # Вспомогательный: статус / сброс / отключение

W_MAIN = 2.0       # основная линия
W_SEC = 1.5        # второстепенная линия
W_FINE = 1.2       # контур / деталь
W_BADGE = 2.4      # штрих глифа-модификатора
RX = 1.4           # единый радиус скругления

CANVAS = 32
BADGE_C = 24.0     # центр глифа-модификатора (правый нижний угол)
BADGE_CUT = 7.6    # радиус «высечки» базового слоя под модификатором

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_DIR = os.path.join(ROOT, "svg")


def n(v) -> str:
    """Компактное форматирование чисел."""
    s = f"{float(v):.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ---------------------------------------------------------------------------
# ПРИМИТИВЫ
# ---------------------------------------------------------------------------

def _stroke(c, w, cap="round", join="round"):
    if c is None:
        return ""
    return (f' stroke="{c}" stroke-width="{n(w)}"'
            f' stroke-linecap="{cap}" stroke-linejoin="{join}"')


def ln(x1, y1, x2, y2, c=BASE, w=W_MAIN):
    return (f'<path d="M {n(x1)},{n(y1)} L {n(x2)},{n(y2)}" fill="none"'
            + _stroke(c, w) + "/>")


def pline(pts, c=BASE, w=W_MAIN, fill="none", closed=False):
    d = "M " + " L ".join(f"{n(x)},{n(y)}" for x, y in pts) + (" Z" if closed else "")
    return f'<path d="{d}" fill="{fill}"' + _stroke(c, w) + "/>"


def shape(pts, fill=BASE, c=None, w=W_FINE):
    return pline(pts, c=c, w=w, fill=fill, closed=True)


def path(d, fill="none", c=None, w=W_MAIN, evenodd=False):
    fr = ' fill-rule="evenodd"' if evenodd else ""
    return f'<path d="{d}" fill="{fill}"{fr}' + _stroke(c, w) + "/>"


def rect(x, y, w, h, fill=BASE, c=None, sw=W_FINE, rx=RX):
    return (f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}"'
            f' rx="{n(rx)}" fill="{fill}"' + _stroke(c, sw) + "/>")


def circ(cx, cy, r, fill=BASE, c=None, w=W_FINE):
    return (f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="{fill}"'
            + _stroke(c, w) + "/>")


def dots(pts, r=1.9, fill=ACC):
    return "".join(circ(x, y, r, fill) for x, y in pts)


def polar(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def arc_d(cx, cy, r, a0, a1):
    """Дуга по часовой стрелке от a0 до a1 (градусы, ось Y вниз)."""
    x0, y0 = polar(cx, cy, r, a0)
    x1, y1 = polar(cx, cy, r, a1)
    large = 1 if (a1 - a0) % 360 > 180 else 0
    return (f"M {n(x0)},{n(y0)} A {n(r)},{n(r)} 0 {large} 1 {n(x1)},{n(y1)}")


def arrow(x1, y1, x2, y2, c=ACC, w=2.2, hs=3.4):
    """Линия с треугольным наконечником в точке (x2,y2)."""
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    bx, by = x2 - ux * hs, y2 - uy * hs
    shaft = ln(x1, y1, bx + ux * 0.6, by + uy * 0.6, c, w)
    head = shape([(x2, y2),
                  (bx + nx * hs * 0.62, by + ny * hs * 0.62),
                  (bx - nx * hs * 0.62, by - ny * hs * 0.62)], c)
    return shaft + head


def circ_arrow(cx, cy, r, a0, a1, c=ACC, w=W_SEC, hs=3.0):
    """Круговая стрелка (обновление / сброс / перезагрузка)."""
    body = path(arc_d(cx, cy, r, a0, a1), c=c, w=w)
    px, py = polar(cx, cy, r, a1)
    a = math.radians(a1)
    tx, ty = -math.sin(a), math.cos(a)      # касательная при возрастании угла
    nx, ny = -ty, tx
    head = shape([(px + tx * hs, py + ty * hs),
                  (px + nx * hs * 0.60, py + ny * hs * 0.60),
                  (px - nx * hs * 0.60, py - ny * hs * 0.60)], c)
    return body + head


# --- Канонический знак высотной отметки (ГОСТ-подобный: полка + выноска + стрелка)
# Повторяется во всех «отметочных» иконках — главный носитель стиля набора.

def mark(x, y, s=1.0, fill=ACC, double=False, rot=0.0):
    """
    Знак отметки: остриё в точке (x,y), треугольник, выноска, полка.
    s — масштаб, double — двойная полка (H и Z), rot — поворот вокруг остриё.
    """
    tw, th = 3.1 * s, 5.2 * s          # полуширина и высота треугольника
    stem = 2.4 * s                     # длина выноски
    sw = 3.4 * s                       # полуширина полки
    lw = max(1.3, min(2.2, 1.7 * s))   # толщина линий держится в диапазоне набора
    top = y - th - stem
    g = shape([(x, y), (x - tw, y - th), (x + tw, y - th)], fill)
    g += ln(x, y - th, x, top, fill, lw)
    g += ln(x - sw, top, x + sw, top, fill, lw)
    if double:
        g += ln(x, top, x, top - stem, fill, lw)
        g += ln(x - sw, top - stem, x + sw, top - stem, fill, lw)
    if rot:
        g = f'<g transform="rotate({n(rot)} {n(x)} {n(y)})">{g}</g>'
    return g


# --- Кривые рельефа (ЦМР / горизонтали). Общая форма для всего семейства.

def terrain(dy=0.0, x0=3.0, x1=29.0):
    """Плавная кривая рельефа, масштабируемая по X."""
    pts = [(3, 9), (7, 4.5), (11, 11), (16, 7.5), (21, 4), (25, 10), (29, 6.5)]
    k = (x1 - x0) / 26.0
    p = [(x0 + (x - 3) * k, y + dy) for x, y in pts]
    return (f"M {n(p[0][0])},{n(p[0][1])} C {n(p[1][0])},{n(p[1][1])} "
            f"{n(p[2][0])},{n(p[2][1])} {n(p[3][0])},{n(p[3][1])} "
            f"C {n(p[4][0])},{n(p[4][1])} {n(p[5][0])},{n(p[5][1])} "
            f"{n(p[6][0])},{n(p[6][1])}")


CONTOUR = [(4, 10), (11, 4), (24, 6), (29, 15), (25, 26), (12, 28), (4, 21)]


def sheet(x, y, w, h, fold=6.0, fill=BASE):
    """Лист/документ с загнутым углом."""
    d = (f"M {n(x)},{n(y)} H {n(x + w - fold)} L {n(x + w)},{n(y + fold)} "
         f"V {n(y + h)} H {n(x)} Z")
    g = path(d, fill, OUT, W_FINE)
    g += path(f"M {n(x + w - fold)},{n(y)} V {n(y + fold)} H {n(x + w)}",
              "none", OUT, W_FINE)
    return g


def manhole(cx, cy, r, fill=BASE, ring=OUT):
    """Колодец: кольцо + внутреннее кольцо."""
    return circ(cx, cy, r, fill, ring, W_FINE) + circ(cx, cy, r * 0.46, "none", ring, W_FINE)


# ---------------------------------------------------------------------------
# ГЛИФЫ-МОДИФИКАТОРЫ (правый нижний угол, центр 0,0 → translate(24,24))
# ---------------------------------------------------------------------------

def slashed(glyph, c, uid, ext=5.0, sw=2.2, gap=3.8):
    """Глиф + диагональный запрет с чистой «высечкой» (чтобы не сливался в пятно)."""
    mid = f"sl-{uid}"
    d = f"M {n(-ext)},{n(-ext)} L {n(ext)},{n(ext)}"
    return (
        f'<defs><mask id="{mid}" maskUnits="userSpaceOnUse" x="-8" y="-8" width="16" height="16">'
        f'<rect x="-8" y="-8" width="16" height="16" fill="#fff"/>'
        f'<path d="{d}" fill="none" stroke="#000" stroke-width="{n(gap)}" stroke-linecap="round"/>'
        f'</mask></defs>'
        f'<g mask="url(#{mid})">{glyph}</g>' + ln(-ext, -ext, ext, ext, c, sw)
    )


def hollow_band(d, wo, wi, c, uid):
    """Полая полоса заданной ширины — контур буферной зоны вокруг оси."""
    mid = f"band-{uid}"
    return (
        f'<defs><mask id="{mid}" maskUnits="userSpaceOnUse" x="-6" y="-6" width="44" height="44">'
        f'<rect x="-6" y="-6" width="44" height="44" fill="#fff"/>'
        f'<path d="{d}" fill="none" stroke="#000" stroke-width="{n(wi)}"'
        f' stroke-linecap="round" stroke-linejoin="round"/>'
        f'</mask></defs>'
        f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{n(wo)}"'
        f' stroke-linecap="round" stroke-linejoin="round" mask="url(#{mid})"/>'
    )


def badge_glyph(kind, c, uid="b"):
    w = W_BADGE
    if kind == "plus":
        return ln(-4.6, 0, 4.6, 0, c, w) + ln(0, -4.6, 0, 4.6, c, w)
    if kind == "cross":
        return ln(-3.7, -3.7, 3.7, 3.7, c, w) + ln(3.7, -3.7, -3.7, 3.7, c, w)
    if kind == "check":
        return pline([(-4.5, 0.3), (-1.5, 3.4), (4.6, -3.5)], c, w)
    if kind == "down":
        return arrow(0, -5.2, 0, 5.4, c, w, 3.6)
    if kind == "up":
        return arrow(0, 5.2, 0, -5.4, c, w, 3.6)
    if kind == "stop":
        return rect(-3.7, -3.7, 7.4, 7.4, c, rx=1.2)
    if kind == "pencil":
        return path("M -5.2,5.2 L -4.1,1.5 L 1.9,-4.5 L 4.7,-1.7 L -1.3,4.3 Z", c)
    if kind == "bolt":
        return path("M 1.4,-5.6 L -3.7,0.9 L -0.5,0.9 L -1.5,5.6 L 3.7,-1.1 L 0.5,-1.1 Z", c)
    if kind == "bolt_off":
        return slashed(
            path("M 2.0,-5.8 L -4.2,1.2 L -0.6,1.2 L -2.0,5.8 L 4.2,-1.4 L 0.6,-1.4 Z",
                 "none", c, 1.8),
            c, uid, ext=5.4, sw=2.0, gap=2.8)
    if kind == "eye":
        return (path("M -5.5,0 C -3,-3.7 3,-3.7 5.5,0 C 3,3.7 -3,3.7 -5.5,0 Z", "none", c, 1.7)
                + circ(0, 0, 1.7, c))
    if kind == "eye_off":
        g = (path("M -5.5,0 C -3,-3.7 3,-3.7 5.5,0 C 3,3.7 -3,3.7 -5.5,0 Z", "none", c, 1.7)
             + circ(0, 0, 1.5, c))
        return slashed(g, c, uid, ext=5.4)
    if kind == "refresh":
        return circ_arrow(0, 0, 4.5, -55, 215, c, 2.0, 3.0)
    if kind == "drop":
        return path("M 0,-5.6 C 2.6,-2.3 4.5,-0.5 4.5,1.5 "
                    "A 4.5,4.5 0 1 1 -4.5,1.5 C -4.5,-0.5 -2.6,-2.3 0,-5.6 Z", c)
    if kind == "list":
        return (ln(-4.6, -3.4, 4.6, -3.4, c, 2.0) + ln(-4.6, 0, 4.6, 0, c, 2.0)
                + ln(-4.6, 3.4, 4.6, 3.4, c, 2.0))
    if kind == "pm":
        return (ln(-4.2, -2.3, 4.2, -2.3, c, 2.3) + ln(0, -6.0, 0, 1.4, c, 2.3)
                + ln(-4.2, 4.2, 4.2, 4.2, c, 2.3))
    if kind == "plus_one":
        g = ln(-5.4, -0.4, -1.4, -0.4, c, 2.2) + ln(-3.4, -2.4, -3.4, 1.6, c, 2.2)
        g += pline([(1.0, -2.6), (2.9, -4.0), (2.9, 4.0)], c, 2.2)
        return g
    raise KeyError(kind)


def compose(base_svg, kind=None, color=ACC, uid="i"):
    """Двухслойная композиция: база + модификатор с чистой «высечкой»."""
    if kind is None:
        return base_svg
    mid = f"cut-{uid}"
    return (
        f'<defs><mask id="{mid}" maskUnits="userSpaceOnUse" x="0" y="0" width="32" height="32">'
        f'<rect width="32" height="32" fill="#fff"/>'
        f'<circle cx="{n(BADGE_C)}" cy="{n(BADGE_C)}" r="{n(BADGE_CUT)}" fill="#000"/>'
        f'</mask></defs>'
        f'<g mask="url(#{mid})">{base_svg}</g>'
        f'<g transform="translate({n(BADGE_C)} {n(BADGE_C)})">{badge_glyph(kind, color, uid)}</g>'
    )


# ---------------------------------------------------------------------------
# РЕЕСТР ИКОНОК
# ---------------------------------------------------------------------------

ICONS: list[dict] = []


def icon(cmd, file, group, title, desc, body, badge=None, bcolor=ACC, src="lisp", origin=""):
    ICONS.append(dict(cmd=cmd, file=file, group=group, title=title, desc=desc,
                      body=body, badge=badge, bcolor=bcolor, src=src, origin=origin))


G1 = "Точки и отметки"
G2 = "Рисование"
G3 = "ЦМР и рельеф"
G4 = "Коммуникации"
G5 = "Спец. инструменты"
G6 = "Автоматизация"
G7 = "Оформление чертежа"
G8 = "Настройки и обслуживание"

# ============================================================ G1: Точки и отметки

# z2sp92 — точки/объекты с Z → блок СП_9.2
icon("IGI_z2sp92", "IGI_z2sp92", G1, "Точки в отметки",
     "Объекты с координатой Z → блок СП_9.2",
     dots([(6, 8), (6, 16), (6, 24)], 1.9, NEU)
     + arrow(11.5, 16, 20.4, 16, ACC, 2.2, 3.6)
     + mark(25.5, 26.5, 1.0, ACC),
     src="lisp", origin="IGI_z2sp92.lsp")

# z2sp652 — пары объектов → блок СП_6.5.2 (H верх / Z низ)
icon("IGI_z2sp652", "IGI_z2sp652", G1, "Точки в отметки бордюра",
     "Пары объектов → блок СП_6.5.2 с H и Z",
     dots([(5, 9.5), (8.6, 11.6)], 1.7, NEU) + ln(5, 9.5, 8.6, 11.6, NEU, 1.2)
     + dots([(5, 20.5), (8.6, 22.6)], 1.7, NEU) + ln(5, 20.5, 8.6, 22.6, NEU, 1.2)
     + arrow(11.5, 16, 20.4, 16, ACC, 2.2, 3.6)
     + mark(25.5, 27.5, 1.0, ACC, double=True),
     src="lisp", origin="IGI_z2sp652.lsp")

# SP92ToPoints — обратное преобразование: отметки → точки
icon("IGI_SP92ToPoints", "IGI_SP92ToPoints", G1, "Отметки в точки",
     "Блоки СП_9.2 → примитивы Point с Z из атрибута",
     mark(7.5, 26, 1.0, BASE)
     + arrow(13, 16, 21.9, 16, ACC, 2.2, 3.6)
     + dots([(26.5, 8), (26.5, 16), (26.5, 24)], 1.9, ACC),
     src="lisp", origin="IGI_SP92ToPoints.lsp")

# SelectSP92 — найти и подсветить все отметки
_b = (f'<rect x="3" y="6" width="26" height="21.5" rx="1.2" fill="none" stroke="{ACC}"'
      f' stroke-width="1.4" stroke-dasharray="3.2 2.4"/>')
_b += mark(11, 25, 1.0, BASE) + mark(22, 25, 1.0, ACC)
icon("IGI_SelectSP92", "IGI_SelectSP92", G1, "Выбрать отметки",
     "Поиск и подсветка всех блоков СП_9.2", _b,
     src="lisp", origin="IGI_SelectSP92.lsp")

# BlockFan — веер блоков (деревьев) из точки
_b = (ln(16, 26.5, 7, 12, NEU, 1.6) + ln(16, 26.5, 16, 7.5, NEU, 1.6)
      + ln(16, 26.5, 25, 12, NEU, 1.6))
_b += circ(7, 12, 4.2, BASE) + circ(25, 12, 4.2, BASE) + circ(16, 7.5, 4.4, BASE)
_b += circ(16, 26.5, 3.3, ACC)
icon("IGI_BlockFan", "IGI_BlockFan", G1, "Создать веер деревьев",
     "Веер копий блока вокруг точки вставки", _b,
     src="lisp", origin="IGI_BlockFan.lsp")

# block2vertex — блок во все вершины полилинии
_v = [(4, 24), (11, 12), (20, 20), (28, 8)]
_b = pline(_v, BASE, W_MAIN)
for x, y in _v:
    _b += rect(x - 2.1, y - 2.1, 4.2, 4.2, ACC, rx=0.9)
icon("block2vertex", "IGI_BlockToVertex", G1, "Блок по вершинам",
     "Копирование блока во все вершины полилинии", _b,
     src="lisp", origin="BlockToVertex.lsp")

# FIX_Z_SP92 — правка атрибута Z на поправку / по высоте вехи
icon("IGI_FIX_Z_SP92", "IGI_FIX_Z_SP92", G1, "Внести поправки в отметки",
     "Поправка dZ атрибута вручную или по высоте вехи",
     mark(11.5, 27.5, 1.75, BASE),
     badge="pencil", bcolor=MOD, src="lisp", origin="IGI_FIX_Z_SP92.lsp")

# FIX_Z_FROM_ATTR_SP92 — значение атрибута → физическая координата Z
icon("IGI_FIX_Z_FROM_ATTR_SP92", "IGI_FIX_Z_FROM_ATTR_SP92", G1, "Перенести отметки на Z",
     "Значение атрибута Z → координата вставки блока",
     mark(12, 28.5, 1.6, BASE)
     + ln(19.0, 16.3, 24, 16.3, ACC, 1.4)
     + arrow(24, 16.3, 24, 28.5, ACC, 2.2, 3.6),
     src="lisp", origin="IGI_FIX_Z_FROM_ATTR_SP92.lsp")

# Z0 — обнуление всего чертежа на Z=0
icon("IGI_Z0", "igi_z0", G1, "Обнуление чертежа",
     "Проекция всех объектов на плоскость Z=0",
     ln(3, 28, 29, 28, BASE, W_MAIN)
     + pline([(4.5, 6), (15, 6), (4.5, 20), (15, 20)], BASE, 2.6)
     + arrow(24, 5, 24, 22.5, ACC, 2.2, 3.8),
     src="lisp", origin="IGI_Z0.lsp")

# SEQNUM — последовательная нумерация текста по порядку выбора
_d1 = pline([(0, 1.6), (2.2, 0), (2.2, 7.5)], ACC, 2.0)
_d2 = path("M 0,1.4 C 0.2,-0.3 3.9,-0.4 4.0,1.7 C 4.1,3.6 0.6,4.8 0,7.5 L 4.3,7.5", "none", ACC, 2.0)
_d3 = path("M 0,0.4 L 4.0,0.4 L 1.9,3.1 C 4.2,3.1 4.6,5.0 3.7,6.4 C 2.9,7.6 0.8,7.7 0,6.6", "none", ACC, 2.0)
_b = ""
for top, dg in [(4.5, _d1), (12.75, _d2), (21.0, _d3)]:
    _b += f'<g transform="translate(4 {n(top)})">{dg}</g>'
    _b += ln(12, top + 3.75, 28, top + 3.75, BASE, 2.6)
icon("IGI_SEQNUM", "IGI_SEQNUM", G1, "Нумерация текста",
     "Последовательные номера в порядке выбора объектов", _b,
     src="lisp", origin="IGI_Seqnum.lsp")

# SEQNUM_COPY — копирование текста с автоинкрементом +1
icon("IGI_SEQNUM_COPY", "IGI_SEQNUM_COPY", G1, "Копия текста с +1",
     "Копирование текста с увеличением номера на 1",
     rect(3.5, 5, 18, 8, NEU) + rect(7.5, 14, 18, 8, BASE, OUT, W_FINE),
     badge="plus_one", bcolor=ACC, src="lisp", origin="IGI_Seqnum_copy.lsp")

# CleanDynRotate — сброс динамического поворота в базовый Rotation
icon("CleanDynRotate", "IGI_CleanDynRotate", G1, "Очистить динамический поворот",
     "Перенос dyn-поворота в Rotation, пакетно 10000+",
     f'<g transform="rotate(-20 14 14)">{rect(7.5, 7.5, 13, 13, BASE, OUT, W_FINE)}</g>'
     + circ(14, 14, 1.6, OUT),
     badge="refresh", bcolor=STA, src="lisp", origin="CleanDynRotate.lsp")

# Geo_Import — импорт точек из файла (скомпилированный VLX)
icon("Geo_Import", "IGI_GeoImport", G1, "Импорт точек",
     "Импорт точек из файла (Geo_Import VLX)",
     sheet(12, 3, 16, 26, 5.5)
     + dots([(17, 14), (22.5, 18), (17, 22)], 1.7, NEU)
     + arrow(2.5, 16, 10.6, 16, ACC, 2.4, 3.8),
     src="lisp", origin="Geo_Import_v2_10.VLX")

# ============================================================ G2: Рисование

# Podporka — подпорная стенка: зубцы между осью и целевой линией
_b = ln(3, 9, 29, 8, BASE, W_MAIN) + ln(3, 23, 29, 25, BASE, W_MAIN)
for xa, xb in [(4.0, 8.0), (13.5, 17.5), (23.0, 27.0)]:
    yt = 9 - (xa - 3) / 26.0
    yb = 23 + ((xa + xb) / 2 - 3) / 26.0 * 2
    _b += shape([(xa, yt), (xb, yt - 0.15), ((xa + xb) / 2, yb)], ACC)
icon("IGI_Podporka", "IGI_Podporka", G2, "Подпорная стенка",
     "Блоки СП_3.59.2 вдоль оси с дотяжкой до цели", _b,
     src="lisp", origin="IGI_Podporka.lsp")

# FILL_AREA — заполнение контура образцами (шахматный порядок)
_b = shape(CONTOUR, "none", BASE, W_MAIN)
for x, y in [(10, 11), (19, 11), (14.5, 17), (23.5, 17), (10, 23), (19, 23)]:
    _b += rect(x - 1.7, y - 1.7, 3.4, 3.4, ACC, rx=0.8)
icon("IGI_FILL_AREA", "IGI_FILL_AREA", G2, "Заполнение объектами",
     "Расстановка блоков и текста внутри контура", _b,
     src="python", origin="commands/fill_area.py")

# SLOPE_HATCH — штриховка откоса между бровкой и подошвой
_up = [(3, 10), (11, 6), (20, 11), (29, 7)]
_lo = [(3, 23), (11, 19), (20, 24), (29, 20)]


def _y_at(pts, x):
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


_b = pline(_up, BASE, W_MAIN) + pline(_lo, BASE, W_MAIN)
for i, x in enumerate([7, 11, 15.5, 20, 24.5]):
    ya, yb = _y_at(_up, x), _y_at(_lo, x)
    _b += ln(x, ya, x, yb if i % 2 == 0 else ya + (yb - ya) * 0.45, ACC, 1.8)
icon("IGI_SLOPE_HATCH", "IGI_SLOPE_HATCH", G2, "Штриховка откоса",
     "Бергштрихи между бровкой и подошвой откоса", _b,
     src="python", origin="commands/slope_hatch/")

# ============================================================ G3: ЦМР и рельеф

# DEM_MANAGER — менеджер подключённых GeoTIFF
_b = (rect(3, 4, 18, 15, NEU) + rect(7, 8, 18, 15, BASE, OUT, W_FINE)
      + path(terrain(4.0, 9.5, 22.5), "none", OUT, 1.4)
      + path(terrain(9.0, 9.5, 22.5), "none", OUT, 1.4))
icon("IGI_DEM_MANAGER", "IGI_DEM_MANAGER", G3, "Менеджер ЦМР",
     "Подключение GeoTIFF и управление списком ЦМР", _b,
     badge="list", bcolor=ACC, src="python", origin="commands/dem_manager.py")

# DEM_TRACKER — высота поверхности под курсором в реальном времени
_cursor = "M 0,0 L 0,13.4 L 3.4,10.0 L 5.9,14.6 L 8.6,13.2 L 6.1,8.7 L 10.6,8.4 Z"
icon("IGI_DEM_TRACKER", "IGI_DEM_TRACKER", G3, "ЦМР-трекер",
     "Плашка «Z: … м» под курсором в реальном времени",
     path(terrain(-3.0, 3, 20), "none", BASE, W_MAIN)
     + path(terrain(2.0, 3, 20), "none", BASE, W_MAIN)
     + f'<g transform="translate(11.5 13.5)">{path(_cursor, ACC)}</g>'
     + rect(21, 17, 9, 7.5, ACC)
     + ln(23, 20.8, 28, 20.8, OUT, 1.4),
     src="python", origin="commands/dem_tracker.py")

# DEM_TRACKER_STOP — остановить мониторинг
icon("IGI_DEM_TRACKER_STOP", "IGI_DEM_TRACKER_STOP", G3, "Остановить трекер",
     "Выключить отслеживание Z, ЦМР остаётся подключённой",
     path(terrain(-3.0, 3, 22), "none", BASE, W_MAIN)
     + path(terrain(2.0, 3, 22), "none", BASE, W_MAIN)
     + f'<g transform="translate(9 12)">{path(_cursor, NEU)}</g>',
     badge="stop", bcolor=STA, src="python", origin="commands/dem_tracker.py")

# ELEV_MARK — отметка из ЦМР по клику
icon("IGI_ELEV_MARK", "IGI_ELEV_MARK", G3, "Отметка в точке из ЦМР",
     "Блок СП_9.2 с высотой из ЦМР в указанной точке",
     path(terrain(-1.0), "none", BASE, W_MAIN)
     + path(terrain(5.0), "none", BASE, W_MAIN)
     + mark(16, 28.5, 1.3, ACC),
     src="python", origin="commands/elev_mark/mark_point.py")

# ELEV_MARK_LINES — отметки из ЦМР вдоль линий с шагом
_b = ln(3, 26, 29, 10, BASE, W_MAIN)
for t in (0.2, 0.5, 0.8):
    _b += mark(3 + 26 * t, 26 - 16 * t, 0.95, ACC)
icon("IGI_ELEV_MARK_LINES", "IGI_ELEV_MARK_LINES", G3, "Отметки по линии из ЦМР",
     "Расстановка отметок вдоль линий с заданным шагом", _b,
     src="python", origin="commands/elev_mark/mark_lines.py")

# ELEV_MARK_GRID — отметки из ЦМР по сетке внутри контура
_b = shape(CONTOUR, "none", BASE, W_MAIN)
for x, y in [(12, 17), (21, 17), (12, 25), (21, 25)]:
    _b += mark(x, y, 0.8, ACC)
icon("IGI_ELEV_MARK_GRID", "IGI_ELEV_MARK_GRID", G3, "Отметки по сетке из ЦМР",
     "Регулярная сетка отметок внутри замкнутой полилинии", _b,
     src="python", origin="commands/elev_mark/mark_grid.py")

# Interp — интерполяция полуметровых горизонталей между отметками
_b = (path("M 4,11 C 9,6.5 14,13 19,9 C 23,6 26,10 28,8.5", "none", BASE, W_SEC)
      + path("M 4,17 C 9,12.5 14,19 19,15 C 23,12 26,16 28,14.5", "none", BASE, W_SEC)
      + ln(6, 28, 26, 28, NEU, W_SEC)
      + mark(6, 28, 0.9, BASE) + mark(26, 28, 0.9, BASE)
      + dots([(11, 28), (16, 28), (21, 28)], 1.9, ACC))
icon("IGI_Interp", "IGI_Interp", G3, "Интерполяция горизонталей",
     "Горизонтали с шагом 0,5 м между блоками СП_9.2", _b,
     src="lisp", origin="IGI_Interp.lsp")

# ============================================================ G4: Коммуникации

# KolodecCalcZ — пересчёт Z1–Z4 как Z + дельта
icon("IGI_KolodecCalcZ", "IGI_KolodecCalcZ", G4, "Высчитать отметки труб",
     "Пересчёт Z1–Z4 колодца по формулам и дельтам",
     manhole(13, 14.5, 9.5),
     badge="pm", bcolor=ACC, src="lisp", origin="IGI_KolodecCalcZ.lsp")

# InsertKolodecAttrBlockText — вклинить значение в цепочку атрибутов
_b = (rect(3.5, 21, 6.5, 6.5, BASE) + rect(12.5, 21, 6.5, 6.5, BASE)
      + rect(21.5, 21, 6.5, 6.5, BASE)
      + rect(8, 4, 6.5, 6.5, ACC)
      + arrow(11.25, 12, 11.25, 19.6, ACC, 2.2, 3.4))
icon("IGI_InsertKolodecAttrBlockText", "IGI_InsertKolodecAttrBlockText", G4,
     "Вклинить отметку", "Вставка значения в цепочку Z1–Z4 со сдвигом", _b,
     src="lisp", origin="IGI_InsertKolodecAttrBlockText.lsp")

# BringKolodecBlocksToFront — порядок прорисовки: колодцы поверх всего
icon("IGI_BringKolodecBlocksToFront", "IGI_BringKolodecBlocksToFront", G4,
     "Люки на передний план", "DRAWORDER: блоки колодцев поверх других объектов",
     rect(3.5, 3.5, 17, 17, NEU) + rect(8, 8, 17, 17, BASE, OUT, W_FINE)
     + manhole(15, 15, 4.4),
     badge="up", bcolor=ACC, src="lisp", origin="IGI_BringKolodecBlocksToFront.lsp")

# ============================================================ G5: Спец. инструменты

# GZU_FROM_GEOJSON — импорт границ землепользования
_gzu = [(5, 26), (10, 5), (26, 9), (23, 22)]
_b = shape(_gzu, "none", BASE, W_MAIN) + dots(_gzu, 2.0, BASE)
icon("IGI_GZU_FROM_GEOJSON", "IGI_GZU_FROM_GEOJSON", G5, "Импорт GeoJSON",
     "Границы ГЗУ из GeoJSON + блоки СП_1.5 по вершинам", _b,
     badge="down", bcolor=ACC, src="python", origin="commands/gzu_from_geojson.py")

# DRAW_NOMENCLATURE — разграфка 250×250 м с подписями листов
_b = rect(3.5, 3.5, 25, 25, "none", BASE, W_MAIN, rx=1.0)
for v in (12, 20.5):
    _b += ln(v, 3.5, v, 28.5, BASE, 1.3) + ln(3.5, v, 28.5, v, BASE, 1.3)
_b += rect(12, 12, 8.5, 8.5, ACC, rx=0.4)
_b += ln(13.9, 15.2, 18.9, 15.2, OUT, 1.3) + ln(13.9, 17.8, 17.2, 17.8, OUT, 1.3)
icon("IGI_DRAW_NOMENCLATURE", "IGI_DRAW_NOMENCLATURE", G5, "Построение номенклатуры",
     "Сетка листов 250×250 м с подписями номенклатуры", _b,
     src="python", origin="commands/draw_nomenclature/")

# BUFFER_POLY — объединённые буферные зоны вокруг линий
_bp = "M 7,24 L 14,13 L 25,17"
icon("IGI_BUFFER_POLY", "IGI_BUFFER_POLY", G5, "Граница буфера",
     "Замкнутые буферные полигоны вокруг линий, с объединением",
     hollow_band(_bp, 9.0, 6.0, ACC, "buffer") + path(_bp, "none", BASE, W_MAIN),
     src="python", origin="commands/buffer_poly.py")

# GETTOTALAREAOFNESTEDPOLYGONS — площадь с учётом отверстий
_outer = "M 3,22 L 7,5 L 21,3 L 29,12 L 26,25 L 10,29 Z"
_hole = "M 9,17 L 12,9 L 21,8 L 23,16 L 18,22 L 11,22 Z"
_island = "M 13,16 L 15,11.5 L 19,12 L 19.5,17 L 15.5,18.5 Z"
icon("IGI_GETTOTALAREAOFNESTEDPOLYGONS", "IGI_GetTotalAreaOfNestedPolygons", G5,
     "Площадь группы полигонов", "Суммарная площадь с вычетом отверстий",
     path(_outer + " " + _hole, BASE, OUT, W_FINE, evenodd=True)
     + path(_island, ACC, OUT, W_FINE),
     src="python", origin="commands/get_total_area_of_nested_polygons.py")

# ============================================================ G6: Автоматизация

# ALIGN_SP92 — разворот подписей параллельно опорной линии
_ang = math.degrees(math.atan2(-16, 26))
_b = ln(3, 25, 29, 9, BASE, W_MAIN)
for t in (0.28, 0.72):
    _b += mark(3 + 26 * t, 25 - 16 * t, 0.95, ACC, rot=_ang)
icon("IGI_ALIGN_SP92", "IGI_ALIGN_SP92", G6, "Отметки вдоль линии",
     "Разворот подписей СП_9.2 / СП_6.5.2 вдоль кривой", _b,
     src="python", origin="commands/align_sp92.py")

# register_reactor_auto_align_sp92 — автоповорот включён
_auto_base = (ln(3, 25, 29, 9, BASE, W_MAIN)
              + mark(13, 18.85, 0.95, BASE, rot=_ang))
icon("IGI_register_reactor_auto_align_sp92", "IGI_AUTO_ALIGN_ON", G6,
     "Автоповорот отметок — вкл.", "Реактор на MOVE/COPY для слоя дорожной сети",
     _auto_base, badge="bolt", bcolor=PRC,
     src="python", origin="commands/auto_align_sp92.py")

# unregister_reactor_auto_align_sp92 — автоповорот выключен
icon("IGI_unregister_reactor_auto_align_sp92", "IGI_AUTO_ALIGN_OFF", G6,
     "Автоповорот отметок — выкл.", "Отключение реактора автовыравнивания",
     _auto_base, badge="bolt_off", bcolor=STA,
     src="python", origin="commands/auto_align_sp92.py")

# ============================================================ G7: Оформление чертежа

# SetLayerColors — 4 служебных слоя получают условные цвета
_LY = [4.0, 10.6, 17.2, 23.8]
_b = "".join(rect(3, y, 26, 5, c, rx=1.4)
             for y, c in zip(_LY, [STA, PRC, ACC, MOD]))
icon("IGI_SetLayerColors", "IGI_SetLayerColors", G7, "Раскрасить слои",
     "Условные цвета слоёв 02, 15, 18, 19", _b,
     src="lisp", origin="IGI_SetLayerColors.lsp")

# ResetLayerColors — сброс цветов слоёв на белый
_b = "".join(rect(3, y, 26, 5, BASE, rx=1.4) for y in _LY)
icon("IGI_ResetLayerColors", "IGI_ResetLayerColors", G7, "Сбросить раскраску слоёв",
     "Возврат цветов служебных слоёв к белому (7)", _b,
     badge="refresh", bcolor=STA, src="lisp", origin="IGI_ResetLayerColors.lsp")

# SetManholeColors — цвет блоков колодцев «По слою»
icon("IGI_SetManholeColors", "IGI_SetManholeColors", G7, "Раскрасить люки",
     "Color = ByLayer для блоков канализационных колодцев",
     manhole(13, 14, 9.5),
     badge="drop", bcolor=ACC, src="lisp", origin="IGI_SetManholeColors.lsp")

# ResetManholeColors — сброс цвета блоков колодцев
icon("IGI_ResetManholeColors", "IGI_ResetManholeColors", G7, "Сбросить раскраску люков",
     "Возврат цвета блоков колодцев к исходному",
     manhole(13, 14, 9.5),
     badge="refresh", bcolor=STA, src="lisp", origin="IGI_ResetManholeColors.lsp")

# WipeoutCuff — скрыть маскировки внутри блоков (ускорение прорисовки)
_mask_base = (ln(3, 12, 29, 12, NEU, 2.4) + ln(3, 18, 29, 18, NEU, 2.4)
              + rect(8, 6, 17, 16, BASE, OUT, W_FINE))
icon("IGI_WipeoutCuff", "IGI_DisableMasks", G7, "Отключить маскировки",
     "Скрыть Wipeout в блоках — быстрее регенерация", _mask_base,
     badge="eye_off", bcolor=STA, src="lisp", origin="IGI_WipeoutVisibility.lsp")

# WipeoutUncuff — вернуть маскировки (сдача чертежа)
icon("IGI_WipeoutUncuff", "IGI_RestoreMasks", G7, "Восстановить маскировки",
     "Вернуть видимость Wipeout по шаблону СП", _mask_base,
     badge="eye", bcolor=PRC, src="lisp", origin="IGI_WipeoutVisibility.lsp")

# ============================================================ G8: Настройки и обслуживание

# LOAD_TEMPLATE — загрузить свой DWG как template.dwg
_tpl = (sheet(6, 3, 20, 26, 6.0)
        + shape([(11.5, 13), (15.5, 19.5), (7.5, 19.5)], "none", OUT, 1.4)
        + circ(19.5, 17, 2.8, "none", OUT, 1.4))
icon("IGI_LOAD_TEMPLATE", "IGI_LOAD_TEMPLATE", G8, "Загрузить шаблон СП",
     "Свой DWG → template.dwg (старый → .bak)", _tpl,
     badge="down", bcolor=ACC, src="python", origin="commands/manage_template.py")

# RESET_TEMPLATE — вернуть заводской шаблон
icon("IGI_RESET_TEMPLATE", "IGI_RESET_TEMPLATE", G8, "Сбросить шаблон СП",
     "Возврат заводского template.default.dwg", _tpl,
     badge="refresh", bcolor=STA, src="python", origin="commands/manage_template.py")

# CHECK_UPDATE — проверка новой версии на GitHub
icon("IGI_CHECK_UPDATE", "IGI_CHECK_UPDATE", G8, "Обновление",
     "Проверка новой версии IGI Tools на GitHub",
     circ_arrow(12.5, 12.5, 8.0, -10, 280, ACC, 2.6, 4.0),
     badge="check", bcolor=PRC, src="python", origin="commands/check_update.py")

# RELOAD_ALL — перезагрузка модулей команд (разработка)
icon("IGI_RELOAD_ALL", "IGI_RELOAD_ALL", G8, "Перезагрузить модули",
     "importlib.reload всех модулей команд (для разработки)",
     rect(3.5, 4, 17, 13, NEU) + rect(7.5, 8.5, 17, 13, BASE, OUT, W_FINE)
     + ln(11, 13, 21, 13, OUT, 1.3) + ln(11, 17, 18, 17, OUT, 1.3),
     badge="refresh", bcolor=PRC, src="python", origin="commands/reload_all.py")

# --- Служебные иконки интерфейса (не команды, но нужны вкладке и документам)

icon("IGI_TOOLS_BRAND", "IGI_Tools", G8, "Знак плагина",
     "Иконка вкладки ленты, установщика и документации",
     rect(3, 3, 26, 26, "none", BASE, W_MAIN, rx=5.0)
     + path(terrain(13.0, 7, 25), "none", BASE, W_SEC)
     + mark(16, 19, 0.95, ACC),
     src="ui", origin="ui/igi_tools.cuix")

icon("IGI_HELP", "IGI_HELP", G8, "Справка",
     "Кнопка «Справка» — открывает документацию плагина",
     circ(16, 16, 12.5, "none", BASE, W_MAIN)
     + path("M 12,12 C 12,8.6 19.6,8.4 19.6,12.6 C 19.6,15.6 16,15.8 16,19", "none", ACC, 2.4)
     + circ(16, 23, 1.6, ACC),
     src="ui", origin="ui/igi_tools.cuix")


# ---------------------------------------------------------------------------
# СБОРКА
# ---------------------------------------------------------------------------

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def build_svg(ic):
    uid = slug(ic["file"])
    inner = compose(ic["body"], ic["badge"], ic["bcolor"], uid)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32"'
        f' role="img" aria-label="{ic["title"]}">\n'
        f'  <title>{ic["cmd"]} — {ic["title"]}</title>\n'
        f'  {inner}\n</svg>\n'
    )


def main():
    os.makedirs(SVG_DIR, exist_ok=True)
    manifest = []
    for ic in ICONS:
        svg = build_svg(ic)
        with open(os.path.join(SVG_DIR, ic["file"] + ".svg"), "w", encoding="utf-8") as f:
            f.write(svg)
        manifest.append({k: ic[k] for k in
                         ("cmd", "file", "group", "title", "desc", "src", "origin")}
                        | {"svg": svg})
    with open(os.path.join(ROOT, "icons.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"SVG: {len(ICONS)} → {SVG_DIR}")
    return manifest


if __name__ == "__main__":
    main()
