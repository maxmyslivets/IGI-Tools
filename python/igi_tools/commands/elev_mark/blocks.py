"""Вставка блоков «СП_9.2»."""

from __future__ import annotations

import traceback

from pyrx import Db, Ed, Rx

from igi_tools.commands.elev_mark.config import BLOCK_NAME
from igi_tools.paths import get_template_path


def _load_template_database(path) -> Db.Database:
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
    """ObjectId блока в чертеже или None."""
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


def _import_block_from_template(db: Db.Database) -> Db.ObjectId | None:
    """Импорт определения «СП_9.2» из template.dwg через wblockCloneObjects."""
    template_path = get_template_path()
    if not template_path.is_file():
        print(f"[IGI Tools] Шаблон не найден: {template_path}")
        return None

    src_id = None
    try:
        src = _load_template_database(template_path)

        src_bt = Db.BlockTable(src.blockTableId(), Db.OpenMode.kForRead)
        try:
            if not src_bt.has(BLOCK_NAME):
                print(f"[IGI Tools] В шаблоне нет блока «{BLOCK_NAME}»: {template_path}")
                return None
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
    except Exception:
        print("[IGI Tools] Не удалось импортировать блок «СП_9.2» из template.dwg.")
        traceback.print_exc()
        return None

    block_id = _get_block_id(db, BLOCK_NAME)
    if block_id is None:
        print("[IGI Tools] Блок СП_9.2 не найден после импорта.")
        return None
    return block_id


def ensure_block(db: Db.Database) -> Db.ObjectId | None:
    """ObjectId блока «СП_9.2» из чертежа или из шаблона; None, если недоступен."""
    block_id = _get_block_id(db, BLOCK_NAME)
    if block_id is not None:
        return block_id
    try:
        return _import_block_from_template(db)
    except Exception:
        traceback.print_exc()
        return None


def insert_mark(db: Db.Database, x: float, y: float, elev: float) -> bool:
    """Вставить блок «СП_9.2» с отметкой Z=elev в точку (x, y). Возвращает True при успехе."""
    block_id = ensure_block(db)
    if block_id is None:
        return False

    # Вставку, динамические свойства и атрибут Z выполняет AutoLISP (IGI_ElevMark_insert.lsp):
    # PyRx-объекты на write-открытом BlockReference давали eWasOpenForWrite.
    for name, value in (("igi_em_x", x), ("igi_em_y", y), ("igi_em_elev", elev)):
        if not Ed.Core.putSym(name, [(Rx.LispType.kDouble, float(value))]):
            print(f"[IGI Tools] Не удалось передать {name} в AutoLISP.")
            return False

    result = Ed.Core.evaluateLisp("(igi-insert-sp92 igi_em_x igi_em_y igi_em_elev)")
    if not (result and len(result) == 1 and result[0] and result[0][0] == Rx.LispType.kT_atom):
        print("[IGI Tools] Вставка блока «СП_9.2» через AutoLISP не удалась.")
        return False
    return True


def _lisp_str_result(expression: str) -> str | None:
    result = Ed.Core.evaluateLisp(expression)
    if not result or len(result) != 1 or not result[0]:
        return None
    item = result[0][0]
    if isinstance(item, tuple) and len(item) == 2 and item[0] == Rx.LispType.kText:
        return str(item[1])
    return None


def undo_last_mark() -> bool:
    """Удалить последний вставленный блок отметки. True — удалён."""
    return _lisp_str_result("(igi-em-undo)") == "OK"


def reset_marks_stack() -> None:
    """Сбросить стек вставленных отметок (перед новым запуском команды)."""
    Ed.Core.evaluateLisp("(igi-em-reset)")
