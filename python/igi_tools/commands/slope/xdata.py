"""XData / Xrecord helpers for slope group persistent data.

RegApp = "IGI_SLOPE"
Dictionary name on Top curve = "IGI_SLOPE_STROKES"
Xrecord key within the dict = "STROKE_HANDLES"

XData layout (all group members):
  [0] (1001, "IGI_SLOPE")          — regapp
  [1] (1000, "Slope")              — marker
  [2] (1000, role)                 — "Top" | "Bottom" | "Stroke"
  [3] (1000, group_guid)           — UUID string

Top extra:
  [4] (1071, num_strokes) int32
  [5] (1040, bottom_offset) double
  [6] (1071, short_count) int32
  [7] (1040, mid_ratio) double
  [8] (1071, use_mid_length) int32
  [9] (1040, mid_length) double
  [10] (1005, bottom_handle) handle

Bottom extra:
  [4] (1005, top_handle) handle

Stroke extra:
  [4] (1000, layer) str
  [5] (1071, stroke_index) int32
  [6] (1070, is_short) int16  (0/1)
  [7] (1005, top_handle) handle
"""

from __future__ import annotations

from uuid import uuid4

from pyrx import Db

REGAPP_NAME = "IGI_SLOPE"
MARKER = "Slope"
DICT_NAME = "IGI_SLOPE_STROKES"
XRECORD_KEY = "STROKE_HANDLES"

ROLE_TOP = "Top"
ROLE_BOTTOM = "Bottom"
ROLE_STROKE = "Stroke"


# ---------------------------------------------------------------------------
# RegApp registration
# ---------------------------------------------------------------------------


def _ensure_regapp(db: Db.Database) -> bool:
    """Register IGI_SLOPE application in the RegApp table if not present."""
    try:
        rat = Db.RegAppTable(db.regAppTableId(), Db.OpenMode.kForRead)
        if rat.has(REGAPP_NAME):
            rat.close()
            return True
        rat.upgradeOpen()
        rec = Db.RegAppTableRecord()
        rec.setName(REGAPP_NAME)
        rat.add(rec)
        rat.close()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# XData builders
# ---------------------------------------------------------------------------


def _make_top_xdata(
    group_guid: str,
    num_strokes: int,
    bottom_offset: float,
    short_count: int,
    mid_ratio: float,
    use_mid_length: bool,
    mid_length: float,
    bottom_handle_str: str,
) -> list[tuple[int, object]]:
    """Build XData list for the Top curve."""
    return [
        (1001, REGAPP_NAME),
        (1000, MARKER),
        (1000, ROLE_TOP),
        (1000, group_guid),
        (1071, num_strokes),
        (1040, bottom_offset),
        (1071, short_count),
        (1040, mid_ratio),
        (1071, int(use_mid_length)),
        (1040, mid_length),
        (1005, bottom_handle_str),
    ]


def _make_bottom_xdata(
    group_guid: str, top_handle_str: str
) -> list[tuple[int, object]]:
    """Build XData list for the Bottom curve."""
    return [
        (1001, REGAPP_NAME),
        (1000, MARKER),
        (1000, ROLE_BOTTOM),
        (1000, group_guid),
        (1005, top_handle_str),
    ]


def _make_stroke_xdata(
    group_guid: str,
    layer: str,
    index: int,
    is_short: bool,
    top_handle_str: str,
) -> list[tuple[int, object]]:
    """Build XData list for a single stroke Line."""
    return [
        (1001, REGAPP_NAME),
        (1000, MARKER),
        (1000, ROLE_STROKE),
        (1000, group_guid),
        (1000, layer),
        (1071, index),
        (1070, -1 if is_short else 0),
        (1005, top_handle_str),
    ]


# ---------------------------------------------------------------------------
# XData readers
# ---------------------------------------------------------------------------


def _read_xdata(entity: Db.Entity) -> list[tuple[int, object]] | None:
    """Read xdata for REGAPP_NAME from entity. Returns list of (code, value) or None."""
    try:
        raw = entity.xData(REGAPP_NAME)
        if raw:
            return raw
        return None
    except Exception:
        return None


def _xdata_get_str(
    xd: list[tuple[int, object]], idx: int
) -> str | None:
    """Get string value at index (must be DxfCode 1000)."""
    if idx < len(xd):
        code, val = xd[idx]
        if code in (1000, 1001):
            return str(val)
    return None


def _xdata_get_int(
    xd: list[tuple[int, object]], idx: int
) -> int | None:
    """Get int value at index (codes 1070, 1071, 90)."""
    if idx < len(xd):
        code, val = xd[idx]
        if code in (1070, 1071, 90):
            return int(val)
    return None


def _xdata_get_double(
    xd: list[tuple[int, object]], idx: int
) -> float | None:
    """Get double value at index (code 1040)."""
    if idx < len(xd):
        code, val = xd[idx]
        if code == 1040:
            return float(val)
    return None


def _xdata_get_handle(
    xd: list[tuple[int, object]], idx: int
) -> str | None:
    """Get handle string at index (code 1005)."""
    if idx < len(xd):
        code, val = xd[idx]
        if code == 1005:
            return str(val)
    return None


# ---------------------------------------------------------------------------
# Extension dictionary / Xrecord helpers
# ---------------------------------------------------------------------------


def _write_stroke_handles(
    tr: Db.Transaction,
    top_oid: Db.ObjectId,
    stroke_handles: list[str],
) -> bool:
    """Write list of stroke handles into Xrecord in Top's extension dict.

    Dictionary name: "IGI_SLOPE_STROKES"
    Xrecord key: "STROKE_HANDLES"
    """
    try:
        top = tr.getObject(top_oid, Db.OpenMode.kForWrite)
        if top.extensionDictionary().isNull():
            top.createExtensionDictionary()

        dict_oid = top.extensionDictionary()
        d = Db.Dictionary(dict_oid, Db.OpenMode.kForWrite)

        # Build data: list of (1000, handle_str)
        data: list[tuple[int, object]] = [
            (1000, h) for h in stroke_handles
        ]

        xrec = Db.Xrecord()
        xrec.setFromRbChain(data)

        d.setAt(XRECORD_KEY, xrec)
        return True
    except Exception:
        return False


def _read_stroke_handles(
    tr: Db.Transaction, top_oid: Db.ObjectId
) -> list[str] | None:
    """Read stroke handles from Top's extension dict Xrecord."""
    try:
        top = tr.getObject(top_oid, Db.OpenMode.kForRead)
        if top.extensionDictionary().isNull():
            return None

        dict_oid = top.extensionDictionary()
        d = Db.Dictionary(dict_oid, Db.OpenMode.kForRead)

        if XRECORD_KEY not in d:
            return None

        xrec_oid = d[XRECORD_KEY]
        xrec = tr.getObject(xrec_oid, Db.OpenMode.kForRead)
        xrec = Db.Xrecord.cast(xrec)
        if xrec is None:
            return None
        rb = xrec.rbChain()
        if not rb:
            return None
        handles = []
        for code, val in rb:
            if code == 1000:
                handles.append(str(val))
        return handles
    except Exception:
        return None


def _remove_stroke_handles(tr: Db.Transaction, top_oid: Db.ObjectId) -> None:
    """Remove the Xrecord and dictionary entry from Top's extension dict."""
    try:
        top = tr.getObject(top_oid, Db.OpenMode.kForWrite)
        if top.extensionDictionary().isNull():
            return

        dict_oid = top.extensionDictionary()
        d = Db.Dictionary(dict_oid, Db.OpenMode.kForWrite)
        if XRECORD_KEY in d:
            d.remove(XRECORD_KEY)
    except Exception:
        pass


def _clear_xdata(entity: Db.Entity) -> None:
    """Clear all IGI_SLOPE xdata from entity."""
    try:
        entity.upgradeOpen()
        # Setting xdata with only the regapp marker removes all data for that app
        entity.setXData([(1001, REGAPP_NAME)])
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Group GUID
# ---------------------------------------------------------------------------


def _new_group_guid() -> str:
    """Generate a new unique group identifier."""
    return str(uuid4())


# ---------------------------------------------------------------------------
# Handle helpers
# ---------------------------------------------------------------------------


def _handle_to_str(obj: Db.Entity) -> str:
    """Convert entity Handle to string."""
    return str(obj.handle())


def _oid_to_handle_str(oid: Db.ObjectId) -> str:
    """Get handle string from ObjectId."""
    return str(oid.handle())


def _try_get_oid_by_handle(
    db: Db.Database, handle_str: str
) -> Db.ObjectId | None:
    """Try to resolve a handle string to an ObjectId."""
    try:
        handle = Db.Handle(handle_str)
        oid = db.getObjectId(False, handle, 0)
        if oid.isValid() and not oid.isNull():
            return oid
    except Exception:
        pass
    return None
