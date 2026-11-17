"""Repair block attributes: sync positions from definition, clean text."""

from __future__ import annotations

import re
import traceback

from pyrx import Db, Ge, command


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------


def _clean_text(text: str) -> str:
    """Remove AutoCAD formatting markers and clean whitespace."""
    text = text.replace("\\P", " ")
    text = re.sub(r"[\r\n\t]", " ", text)
    text = re.sub(r" +", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Attribute definition data extraction (value types only — close DB objects)
# ---------------------------------------------------------------------------


def _get_attr_def_data(
    btr: Db.BlockTableRecord,
) -> dict[str, dict]:
    """Extract (tag, position, alignmentPoint, justify) from all
    AttributeDefinition entities in a BlockTableRecord.

    Returns a dict: {tag: {"position": Ge.Point3d, "alignment_point": Ge.Point3d,
                           "justify": int}}
    """
    data: dict[str, dict] = {}
    for oid in btr.objectIds():
        ent = Db.Entity(oid, Db.OpenMode.kForRead)
        try:
            if not ent.isDerivedFrom(Db.AttributeDefinition.desc()):
                continue
            att_def = Db.AttributeDefinition.cast(ent)
            data[att_def.tag()] = {
                "position": att_def.position(),
                "alignment_point": att_def.alignmentPoint(),
                "justify": att_def.justification(),
            }
        finally:
            ent.close()
    return data


# ---------------------------------------------------------------------------
# Repair (single pass — count + fix)
# ---------------------------------------------------------------------------


def _repair_block_attributes(
    space: Db.BlockTableRecord,
) -> tuple[dict[str, int], int, int]:
    """Repair attributes in all BlockReferences in the given space.

    Returns (counts_per_block, cleaned_texts, synced_positions).
    """
    counts: dict[str, int] = {}
    cleaned_texts = 0
    synced_positions = 0

    for oid in space.objectIds():
        ent = Db.Entity(oid, Db.OpenMode.kForRead)
        if ent.isErased():
            continue
        try:
            if not ent.isDerivedFrom(Db.BlockReference.desc()):
                continue
            br = Db.BlockReference.cast(ent)
            atts = br.attributeIds()
            if atts is None or len(atts) == 0:
                continue

            try:
                # Get block definition attributes
                btr_id = br.blockTableRecord()
                btr = Db.BlockTableRecord(btr_id, Db.OpenMode.kForRead)
                try:
                    attr_defs = _get_attr_def_data(btr)
                    name = btr.name()
                finally:
                    btr.close()

                if not attr_defs:
                    continue

                counts[name] = counts.get(name, 0) + 1

                # Get block transformation matrix
                transform = br.blockTransform()

                # Process each attribute reference
                for att_oid in atts:
                    att_ref = Db.AttributeReference(att_oid, Db.OpenMode.kForRead)
                    try:
                        tag = att_ref.tag()
                        if tag not in attr_defs:
                            continue
                        if att_ref.isConstant():
                            continue
                        def_data = attr_defs[tag]

                        # --- Text cleaning (always) ---
                        original_text = att_ref.textString()
                        cleaned_text = _clean_text(original_text)
                        if original_text != cleaned_text:
                            att_ref.upgradeOpen()
                            try:
                                att_ref.setTextString(cleaned_text)
                            finally:
                                att_ref.downgradeOpen()
                            cleaned_texts += 1

                        # --- Position sync ---
                        ref_pos = att_ref.position()
                        ref_align = att_ref.alignmentPoint()
                        ref_justify = att_ref.justification()

                        def_pos = def_data["position"].transformBy(transform)
                        def_align = def_data["alignment_point"].transformBy(transform)
                        def_justify = def_data["justify"]

                        pos_dirty = ref_pos.distanceTo(def_pos) > 0.1
                        align_dirty = ref_align.distanceTo(def_align) > 0.1
                        justify_dirty = ref_justify != def_justify

                        if pos_dirty or align_dirty or justify_dirty:
                            att_ref.upgradeOpen()
                            try:
                                if pos_dirty:
                                    att_ref.setPosition(def_pos)
                                if align_dirty:
                                    att_ref.setAlignmentPoint(def_align)
                                if justify_dirty:
                                    att_ref.setJustification(def_justify)
                            finally:
                                att_ref.downgradeOpen()
                            synced_positions += 1
                    finally:
                        att_ref.close()
            except Exception:
                # Skip broken blocks without failing the whole command
                continue
        finally:
            ent.close()

    return counts, cleaned_texts, synced_positions


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


@command(name="IGI_REPAIR_ATTRS")
def repair_attrs() -> None:
    """Ремонт атрибутов блоков: синхронизация позиций и очистка текстов.

    Проходит по ModelSpace и PaperSpace, собирает все BlockReference
    с атрибутами, восстанавливает позиции из определения блока
    и очищает текст от управляющих символов.
    """
    print("\n[IGI Tools] Запуск IGI_REPAIR_ATTRS…")

    try:
        db = Db.curDb()

        # ModelSpace — через db.modelSpaceId()
        ms = Db.BlockTableRecord(db.modelSpaceId(), Db.OpenMode.kForRead)

        # PaperSpace — через BlockTable, с защитой на случай отсутствия API
        ps = None
        try:
            bt2 = Db.BlockTable(db.blockTableId(), Db.OpenMode.kForRead)
            ps_id = bt2.paperSpaceId()
            bt2.close()
            ps = Db.BlockTableRecord(ps_id, Db.OpenMode.kForRead)
        except Exception:
            ps = None  # paper space недоступен — пропускаем

        try:
            # Single pass: count + repair
            model_counts, cleaned_model, synced_model = _repair_block_attributes(ms)
            paper_counts: dict[str, int] = {}
            cleaned_paper = 0
            synced_paper = 0
            if ps is not None:
                paper_counts, cleaned_paper, synced_paper = _repair_block_attributes(ps)

            # Merge counts
            all_counts: dict[str, int] = {}
            for name, count in model_counts.items():
                all_counts[name] = all_counts.get(name, 0) + count
            for name, count in paper_counts.items():
                all_counts[name] = all_counts.get(name, 0) + count

            if not all_counts:
                print("[IGI Tools] Блоки с атрибутами не найдены.")
                return

            print("[IGI Tools] Найденные блоки с атрибутами:")
            for name in sorted(all_counts.keys()):
                print(f"  {name} — {all_counts[name]} вхождений")

            grand_total = sum(all_counts.values())
            grand_cleaned = cleaned_model + cleaned_paper
            grand_synced = synced_model + synced_paper

            print(
                f"[IGI Tools] Просмотрено: {grand_total}, "
                f"очищено текстов: {grand_cleaned}, "
                f"синхронизировано позиций: {grand_synced}"
            )
        finally:
            ms.close()
            if ps is not None:
                ps.close()

    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")