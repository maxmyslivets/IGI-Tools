"""Подпись номенклатур планшета в блоке СП_Формуляр.

Команда: IGI_SIGN_NOMENCLATURE

Алгоритм:
  1. Находит вхождение блока "СП_Формуляр" в ModelSpace.
  2. Читает 8 координатных атрибутов (X1,Y1..X4,Y4) — углы квадрата 250×250.
  3. Открывает wx-диалог со всеми полями, предзаполненными из атрибутов.
  4. "Рассчитать автоматически":
     - В блоке X1..X4 = Northing, Y1..Y4 = Easting (российская нотация)
     - центр масс 4 углов → номенклатура планшета
     - смещение центра на ±250 по Northing → номенклатуры выше/ниже
     - смещение центра на ±250 по Easting → номенклатуры справа/слева
     - определение СК по величине координат
  5. "Применить" — записывает все значения в атрибуты блока.
"""

from __future__ import annotations

import traceback

from pyrx import Ap, Db, Ge, Ed, command

from igi_tools.commands.draw_nomenclature.config import (
    detect_coordinate_system,
    calculate_nomenclature,
)

# ─── Работа с блоком СП_Формуляр ────────────────────────────────────


def _get_block_reference() -> Db.BlockReference | None:
    """Найти первое вхождение СП_Формуляр в ModelSpace (открыто на чтение)."""
    db = Db.curDb()
    bt = Db.BlockTable(db.blockTableId(), Db.OpenMode.kForRead)
    try:
        if not bt.has("СП_Формуляр"):
            return None
        btr_id = bt.getAt("СП_Формуляр")
    finally:
        bt.close()

    ms = Db.BlockTableRecord(db.modelSpaceId(), Db.OpenMode.kForRead)
    try:
        for oid in ms.objectIds():
            ent = Db.Entity(oid, Db.OpenMode.kForRead)
            try:
                if ent.isErased():
                    continue
                if not ent.isDerivedFrom(Db.BlockReference.desc()):
                    continue
                br = Db.BlockReference.cast(ent)
                if br.blockTableRecord() == btr_id:
                    return br
            finally:
                ent.close()
    finally:
        ms.close()
    return None


def _read_attributes(br: Db.BlockReference) -> dict[str, str]:
    """Прочитать атрибуты блока в dict tag→value."""
    atts = br.attributeIds()
    if atts is None:
        return {}
    result: dict[str, str] = {}
    for att_oid in atts:
        att_ref = Db.AttributeReference(att_oid, Db.OpenMode.kForRead)
        try:
            result[att_ref.tag()] = att_ref.textString()
        finally:
            att_ref.close()
    return result


def _write_attributes(br: Db.BlockReference, values: dict[str, str]) -> int:
    """Записать значения в атрибуты блока. Возвращает число записанных полей."""
    atts = br.attributeIds()
    if atts is None:
        return 0
    written = 0
    for att_oid in atts:
        att_ref = Db.AttributeReference(att_oid, Db.OpenMode.kForRead)
        try:
            tag = att_ref.tag()
            if tag in values:
                new_val = values[tag]
                if att_ref.textString() != new_val:
                    att_ref.upgradeOpen()
                    try:
                        att_ref.setTextString(new_val)
                    finally:
                        att_ref.downgradeOpen()
                    written += 1
        finally:
            att_ref.close()
    return written


# ─── Расчёт номенклатур ─────────────────────────────────────────────


def _parse_coordinates(attrs: dict[str, str]) -> list[tuple[float, float]] | None:
    """Извлечь (X1,Y1)..(X4,Y4) из атрибутов."""
    required = ("X1", "Y1", "X2", "Y2", "X3", "Y3", "X4", "Y4")
    if not all(k in attrs for k in required):
        return None
    try:
        return [
            (float(attrs["X1"]), float(attrs["Y1"])),
            (float(attrs["X2"]), float(attrs["Y2"])),
            (float(attrs["X3"]), float(attrs["Y3"])),
            (float(attrs["X4"]), float(attrs["Y4"])),
        ]
    except (ValueError, TypeError):
        return None


def _center_of_points(pts: list[tuple[float, float]]) -> tuple[float, float]:
    """Центр масс (среднее арифметическое вершин)."""
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return cx, cy


def _auto_calculate(attrs: dict[str, str]) -> dict[str, str]:
    """Автоматический расчёт полей ПЛАНШЕТ, Ном.Верх/Низ/Справа/Слева,
    СИСТЕМА_КООРДИНАТ по координатам углов планшета."""
    pts = _parse_coordinates(attrs)
    if pts is None:
        return {}

    cx, cy = _center_of_points(pts)

    # В блоке X1..X4 = Northing, Y1..Y4 = Easting (российская нотация)
    easting = cy
    northing = cx

    # Определение системы координат
    minx = min(p[0] for p in pts)
    miny = min(p[1] for p in pts)
    cs = detect_coordinate_system(minx, miny)
    cs_label = "Система координат 1963 г." if cs == "СК63" else "Система координат местная"

    step = 250.0  # размер планшета

    # calculate_nomenclature(x=Easting, y=Northing, ...) — внутри YY=floor(y), XX=floor(x)
    return {
        "ПЛАНШЕТ": calculate_nomenclature(easting, northing, cs),
        "Ном.Верх": calculate_nomenclature(easting, northing + step, cs),
        "Ном.Низ": calculate_nomenclature(easting, northing - step, cs),
        "Ном.Справа": calculate_nomenclature(easting + step, northing, cs),
        "Ном.Слева": calculate_nomenclature(easting - step, northing, cs),
        "СИСТЕМА_КООРДИНАТ": cs_label,
    }


# ─── wxPython диалог ────────────────────────────────────────────────


def _show_dialog(initial: dict[str, str]) -> dict[str, str] | None:
    """Показать диалог редактирования атрибутов.

    Args:
        initial: tag→value из блока (начальные значения полей).

    Returns:
        dict[str, str] с новыми значениями, или None при отмене.
    """
    import wx

    class _SignDialog(wx.Dialog):
        def __init__(self, parent, data: dict[str, str]):
            wx.Dialog.__init__(
                self, parent,
                title="Подпись номенклатур планшета",
                style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP | wx.RESIZE_BORDER,
            )
            self.SetMinSize(wx.Size(480, 500))
            self.result_data: dict[str, str] | None = None

            panel = wx.Panel(self)
            vsizer = wx.BoxSizer(wx.VERTICAL)

            # Описание полей: (ключ, метка, readonly?)
            field_specs = [
                ("ПЛАНШЕТ", "ПЛАНШЕТ (номенклатура планшета)", False),
                ("Ном.Верх", "Ном.Верх (номенклатура выше)", False),
                ("Ном.Низ", "Ном.Низ (номенклатура ниже)", False),
                ("Ном.Справа", "Ном.Справа (номенклатура правее)", False),
                ("Ном.Слева", "Ном.Слева (номенклатура левее)", False),
                ("СИСТЕМА_КООРДИНАТ", "Система координат", False),
                ("МЕСТОПОЛОЖЕНИЕ", "Местоположение (адрес)", False),
                ("МЕСТО", "Место (населённый пункт)", False),
            ]

            self._controls: dict[str, wx.TextCtrl] = {}

            grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=8)
            grid.AddGrowableCol(1, proportion=1)

            for key, label, _readonly in field_specs:
                st = wx.StaticText(panel, label=label)
                ctrl = wx.TextCtrl(panel, value=data.get(key, ""), style=0)
                self._controls[key] = ctrl
                grid.Add(st, flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
                grid.Add(ctrl, flag=wx.EXPAND)

            vsizer.Add(grid, proportion=1, flag=wx.EXPAND | wx.ALL, border=12)

            # Кнопки
            btn_row = wx.BoxSizer(wx.HORIZONTAL)
            calc_btn = wx.Button(panel, label="Рассчитать автоматически")
            calc_btn.Bind(wx.EVT_BUTTON, lambda evt: self._on_calc(evt, data))
            apply_btn = wx.Button(panel, label="Применить")
            apply_btn.Bind(wx.EVT_BUTTON, self._on_apply)

            btn_row.Add(calc_btn, flag=wx.RIGHT, border=8)
            btn_row.Add(apply_btn)
            vsizer.Add(btn_row, flag=wx.ALIGN_CENTER | wx.BOTTOM, border=12)

            panel.SetSizer(vsizer)
            vsizer.Fit(panel)
            self.Fit()
            self.CenterOnScreen()

        def _on_calc(self, evt, data: dict[str, str]):
            """Рассчитать автоматически и заполнить поля."""
            calculated = _auto_calculate(data)
            if not calculated:
                wx.MessageBox(
                    "Не удалось прочитать координаты X1..Y4 из атрибутов блока.\n"
                    "Убедитесь, что атрибуты содержат числовые значения.",
                    "Ошибка", wx.OK | wx.ICON_ERROR
                )
                return
            for key, value in calculated.items():
                if key in self._controls:
                    self._controls[key].SetValue(value)
                    # Обновляем data для повторных нажатий
                    data[key] = value

        def _on_apply(self, evt):
            """Собрать значения и закрыть диалог."""
            result = {}
            for key, ctrl in self._controls.items():
                result[key] = ctrl.GetValue()
            self.result_data = result
            self.EndModal(wx.ID_OK)

    _res = Ap.ResourceOverride()
    dlg = _SignDialog(None, initial)
    if dlg.ShowModal() == wx.ID_OK:
        result = dlg.result_data
        dlg.Destroy()
        return result
    dlg.Destroy()
    return None


# ─── Команда ────────────────────────────────────────────────────────


@command(name="IGI_SIGN_NOMENCLATURE")
def sign_nomenclature() -> None:
    """Подпись номенклатур планшета в блоке СП_Формуляр."""
    print("\n[IGI Tools] Запуск IGI_SIGN_NOMENCLATURE…")

    try:
        # 1. Найти блок
        br = _get_block_reference()
        if br is None:
            print("[IGI Tools] Блок СП_Формуляр не найден в чертеже.")
            return

        try:
            # 2. Прочитать атрибуты
            attrs = _read_attributes(br)
            if not attrs:
                print("[IGI Tools] Атрибуты блока СП_Формуляр не найдены.")
                return

            print("[IGI Tools] Атрибуты прочитаны. Открываю диалог…")

            # 3. Диалог
            result = _show_dialog(attrs)
            if result is None:
                print("[IGI Tools] Операция отменена пользователем.")
                return

            # 4. Записать атрибуты
            written = _write_attributes(br, result)
            print(f"[IGI Tools] Атрибуты обновлены: {written} полей записано.")
        finally:
            br.close()

    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")