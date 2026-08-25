"""
Подключается к запущенному AutoCAD через COM и отправляет команду
IGI_RELOAD_ALL для перезагрузки команд PyRx.
Использует win32com.client.

Коды возврата:
  0 — команда успешно отправлена
  1 — AutoCAD не найден / не запущен (нормального подключения нет)
  2 — подключились, но отправить команду не удалось (реальная ошибка)
"""

import sys

import pythoncom
import win32com.client

# Прог-идентификаторы. Сверху ставьте актуальную для вас версию AutoCAD.
VERSIONS = [
    "AutoCAD.Application.29",  # 2025
    "AutoCAD.Application.28",  # 2024
    "AutoCAD.Application.27",  # 2023
    "AutoCAD.Application.26",  # 2022
    "AutoCAD.Application",     # generic fallback
]

# Команда, которую отправляем. Команды-то с "_" — рабочий вариант.
CMD_STRINGS = [
    "_IGI_RELOAD_ALL \n",
    "IGI_RELOAD_ALL \n",
]


def connect(progid):
    """Возвращает запущенный AutoCAD как COM-объект (или None)."""
    # Сначала привязка к уже работающему инстансу.
    try:
        return win32com.client.GetActiveObject(progid)
    except Exception:
        pass
    # Затем запасной вариант.
    try:
        return win32com.client.GetObject(None, progid)
    except Exception:
        return None


def is_acad_app(obj):
    """Проверяет, что объект действительно является Application AutoCAD."""
    try:
        # У ProgID AutoCAD объект существует и равен чему-то осмысленному.
        name = obj.Name
        return name is not None
    except Exception:
        return False


def main():
    # Инициализация COM в текущем потоке (безопасно и для вызова из других потоков).
    pythoncom.CoInitialize()

    found = False
    for ver in VERSIONS:
        acad = connect(ver)
        if acad is None:
            continue

        # Подтверждаем, что это AutoCAD, а не случайный COM-объект.
        try:
            app_name = acad.Name
        except Exception:
            app_name = None

        if app_name is None:
            print(f"  Объект '{ver}' это не AutoCAD Application, пропускаем.")
            continue

        found = True
        print(f"  AutoCAD найден (COM: {ver})")
        print(f"    Object type: {type(acad).__name__}")

        # small diagnostics
        try:
            print(f"    Application.Name   = {app_name!r}")
        except Exception:
            pass

        ok, method = try_send(acad)
        if ok:
            print(f"  IGI_RELOAD_ALL sent ({method}).")
            return 0

        # Способа/возможности отправить нет. Пытались применить разные пути —
        # показываем реальную картину, а не гадаем про LT.
        print("  Подключение есть, но команду отправить не удалось.")
        print("  Это НЕ признак LT-версии. Возможные причины:")
        print("    - команда IGI_RELOAD_ALL ещё не зарегистрирована в этом сеансе")
        print("      (PyRx/плагин не загружен при старте AutoCAD);")
        print("    - Python 32/64-битность не совпадает с разрядностью AutoCAD;")
        print("    - команда выполняется от имени другого пользователя (UAC).")
        return 2

    if not found:
        print("  AutoCAD не запущен или не доступен по COM (Полный либо LT).")
        return 1

    # Для согласованности с PowerShell-обёрткой возвращаем 1.
    return 1


def _senders(obj):
    """Возвращает список (имя_метода, вызываемая_функция) для объекта obj.

    Управляющие команды шлются через SendCommand / SendStringToExecute.
    В чистом AutoCAD оба есть на Application, а в Civil 3D нужен Document.
    Сигнатура SendStringToExecute(Command, MaxWidth, MaxHeight, EnableCancel).
    """
    return [
        ("SendStringToExecute+args",
         lambda c: obj.SendStringToExecute(c, True, False, False)),
        ("SendStringToExecute",
         lambda c: obj.SendStringToExecute(c)),
        ("SendCommand",
         lambda c: obj.SendCommand(c)),
    ]


def try_send(acad):
    """Отправляет команду на Application и Document. Возвращает (ok, method)."""
    # Document часто является правильной целью для Civil 3D: у него есть
    # SendCommand/SendStringToExecute, которых нет на верхнем Application.
    doc = None
    try:
        doc = acad.ActiveDocument
    except Exception:
        pass

    for label, target in (("Application", acad), ("Document", doc)):
        if target is None:
            continue
        for cmd in CMD_STRINGS:
            for mname, fn in _senders(target):
                try:
                    fn(cmd)
                    return True, f"{label}.{mname}"
                except AttributeError:
                    # Метода нет на конкретном объекте — пробуем следующий.
                    pass
                except Exception as exc:
                    print(f"    {label} {mname}: {type(exc).__name__}: {exc}")

    return False, ""


if __name__ == "__main__":
    rc = main()
    if rc != 0:
        print("  Запустите IGI_RELOAD_ALL вручную в командной строке AutoCAD.")
    sys.exit(rc)