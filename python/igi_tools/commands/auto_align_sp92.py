"""Автовыравнивание блоков СП_9.2 вдоль линии слоя "15 Дорожная сеть" при перемещении.

Работает через EditorReactor — ловит commandWillStart/commandEnded для
MOVE, COPY, STRETCH (включая перемещение за ручку — AutoCAD запускает '_STRETCH).
Сравнивает позиции блоков ДО и ПОСЛЕ, выравнивает только сдвинутые.
"""

from __future__ import annotations

import math
import traceback

from pyrx import Ap, Db, Ed, Ge, command

# --- конфигурация ---
_TARGET_BLOCK = "СП_9.2"
_TARGET_LAYER = "15 Дорожная сеть"
_ANGLE_PROP = "Угол1"
_TOLERANCE_SQ = 0.0001  # ~1 см²

# снапшот блоков ДО команды: {oldId: (x, y)}
_block_snapshot: dict[int, tuple[float, float]] = {}
_reactor: Ed.EditorReactor | None = None
status = None


# --- геометрия (калька с align_sp92) ---

def _normalize_angle_readable(angle: float) -> float:
    angle = angle % (2 * math.pi)
    if angle > math.pi:
        angle -= 2 * math.pi
    if angle > math.pi / 2:
        angle -= math.pi
    elif angle < -math.pi / 2:
        angle += math.pi
    return angle


def _get_curve_tangent_at_point(
    curve: Db.Curve, pt: Ge.Point3d, /
) -> tuple[float | None, float]:
    try:
        closest = curve.getClosestPointTo(pt)
    except Exception:
        return None, float("inf")
    if closest is None:
        return None, float("inf")

    dx = pt.x - closest.x
    dy = pt.y - closest.y
    dist_sq = dx * dx + dy * dy
    if dist_sq > _TOLERANCE_SQ:
        return None, dist_sq

    try:
        param = curve.getParamAtPoint(closest)
        deriv = curve.getFirstDeriv(param)
    except Exception:
        return None, dist_sq
    if deriv is None:
        return None, dist_sq

    tangent = math.atan2(deriv.y, deriv.x)
    return tangent, dist_sq


# --- слепок ---

def _snapshot_blocks() -> None:
    """Запомнить координаты всех блоков СП_9.2."""
    global _block_snapshot
    _block_snapshot.clear()
    db = Db.curDb()
    model = Db.BlockTableRecord(db.modelSpaceId(), Db.OpenMode.kForRead)
    upper = _TARGET_BLOCK.upper()
    try:
        for oid in model:
            try:
                ent = Db.Entity(oid, Db.OpenMode.kForRead)
                if ent.isDerivedFrom(Db.BlockReference.desc()):
                    bref = Db.BlockReference.cast(ent)
                    if bref.effectiveName().upper() == upper:
                        pos = bref.position()
                        _block_snapshot[oid.asOldId()] = (pos.x, pos.y)
                ent.close()
            except Exception:
                pass
    finally:
        model.close()


def _get_moved_blocks() -> list[Db.ObjectId]:
    """Сравнить текущие позиции со слепком — найти сдвинутые блоки."""
    global _block_snapshot
    if not _block_snapshot:
        return []

    moved: list[Db.ObjectId] = []
    db = Db.curDb()
    model = Db.BlockTableRecord(db.modelSpaceId(), Db.OpenMode.kForRead)
    upper = _TARGET_BLOCK.upper()
    try:
        for oid in model:
            try:
                ent = Db.Entity(oid, Db.OpenMode.kForRead)
                if ent.isDerivedFrom(Db.BlockReference.desc()):
                    bref = Db.BlockReference.cast(ent)
                    if bref.effectiveName().upper() != upper:
                        ent.close()
                        continue
                    pos = bref.position()
                    old = _block_snapshot.get(oid.asOldId())
                    if old is None:
                        ent.close()
                        continue  # новый блок (COPY) — пропускаем
                    if abs(pos.x - old[0]) > 0.001 or abs(pos.y - old[1]) > 0.001:
                        moved.append(oid)
                ent.close()
            except Exception:
                pass
    finally:
        model.close()
    _block_snapshot.clear()
    return moved


# --- выравнивание одного блока ---

def _align_one_block(bref_id: Db.ObjectId) -> bool:
    """Выровнять блок СП_9.2 вдоль ближайшей кривой на целевом слое."""
    db = Db.curDb()
    model = Db.BlockTableRecord(db.modelSpaceId(), Db.OpenMode.kForRead)
    curves: list[Db.Entity] = []
    try:
        for oid in model:
            ent = Db.Entity(oid, Db.OpenMode.kForRead)
            try:
                if ent.isDerivedFrom(Db.Curve.desc()) and ent.layer() == _TARGET_LAYER:
                    curves.append(ent)
                else:
                    ent.close()
            except Exception:
                try:
                    ent.close()
                except Exception:
                    pass

        if not curves:
            return False

        bref = Db.BlockReference(bref_id, Db.OpenMode.kForRead)
        try:
            pos = bref.position()
            bref.close()

            best_angle = None
            best_dist_sq = float("inf")

            for curve_ent in curves:
                try:
                    curve = Db.Curve.cast(curve_ent)
                    angle, dist_sq = _get_curve_tangent_at_point(curve, pos)
                    if angle is not None and dist_sq < best_dist_sq:
                        best_dist_sq = dist_sq
                        best_angle = angle
                except Exception:
                    continue

            if best_angle is None:
                return False

            text_angle = _normalize_angle_readable(best_angle)

            bref = Db.BlockReference(bref_id, Db.OpenMode.kForRead)
            is_dyn = bref.isDynamicBlock()
            dyn_props = bref.getBlockProperties() if is_dyn else None
            bref.upgradeOpen()

            if is_dyn and dyn_props:
                has_angle = False
                for prop in dyn_props:
                    name = prop.propertyName()
                    if name == "Положение X" and not prop.readOnly():
                        prop.setValue(Db.EvalVariant(0.0))
                    elif name == "Положение Y" and not prop.readOnly():
                        prop.setValue(Db.EvalVariant(0.0))
                    elif name == _ANGLE_PROP and not prop.readOnly():
                        prop.setValue(Db.EvalVariant(text_angle))
                        has_angle = True
                if not has_angle:
                    bref.setRotation(text_angle)
            else:
                bref.setRotation(text_angle)

            bref.close()
            print(
                f"[IGI Tools] ✓ Блок СП_9.2 на ({pos.x:.2f}, {pos.y:.2f})"
                f" выровнен вдоль '{_TARGET_LAYER}'."
            )
            return True

        except Exception:
            try:
                bref.close()
            except Exception:
                pass
            return False

    finally:
        model.close()
        for c in curves:
            try:
                c.close()
            except Exception:
                pass


# --- EditorReactor (ловит MOVE, COPY, STRETCH, в т.ч. за ручку) ---

class _AutoAlignReactor(Ed.EditorReactor):
    """Реагирует на начало/конец MOVE/COPY/STRETCH."""

    def __init__(self) -> None:
        Ed.EditorReactor.__init__(self)
        print("[IGI Tools]   EditorReactor запущен: слежу за MOVE/COPY/STRETCH.")

    def commandWillStart(self, cmdStr: str) -> None:
        if cmdStr.upper() in ("MOVE", "COPY", "STRETCH", "'_STRETCH"):
            _snapshot_blocks()

    def commandEnded(self, cmdStr: str) -> None:
        if cmdStr.upper() in ("MOVE", "COPY", "STRETCH", "'_STRETCH"):
            try:
                moved = _get_moved_blocks()
                if not moved:
                    return
                for oid in moved:
                    _align_one_block(oid)
            except Exception:
                traceback.print_exc()


# --- публичные функции ---
@command(name="IGI_register_reactor_auto_align_sp92", flags=Ap.CmdFlags.USEPICKSET | Ap.CmdFlags.REDRAW)
def register_reactor() -> None:
    """Зарегистрировать EditorReactor."""
    global _reactor

    global status
    if status is not None:
        unregister_reactor()
        return
    status = True

    if _reactor is None:
        print("[IGI Tools] Регистрация EditorReactor СП_9.2...")
        _reactor = _AutoAlignReactor()
        _reactor.addReactor()
        print("[IGI Tools] ✓ Реактор СП_9.2: EditorReactor запущен.")
    else:
        print("[IGI Tools]   Реактор уже зарегистрирован.")

@command(name="IGI_unregister_reactor_auto_align_sp92", flags=Ap.CmdFlags.USEPICKSET | Ap.CmdFlags.REDRAW)
def unregister_reactor() -> None:
    """Отменить регистрацию реактора."""
    global _reactor

    global status
    status = None

    if _reactor is not None:
        try:
            _reactor.removeReactor()
        except Exception:
            pass
        _reactor = None
        print("[IGI Tools] ✓ Реактор СП_9.2 остановлен.")
