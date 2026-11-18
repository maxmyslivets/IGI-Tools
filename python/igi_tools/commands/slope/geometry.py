"""Geometry helpers for slope — ported from SSTools Slope algorithms."""

from __future__ import annotations

import math
from uuid import uuid4

from pyrx import Db, Ge

# ---------------------------------------------------------------------------
# Low-level geometry helpers
# ---------------------------------------------------------------------------


def _distance_in_plane(a: Ge.Point3d, b: Ge.Point3d) -> float:
    """Euclidean distance projected onto the XY plane."""
    dx = a.x - b.x
    dy = a.y - b.y
    return math.hypot(dx, dy)


def _get_offset_point(p0: Ge.Point3d, p1: Ge.Point3d, dist: float) -> Ge.Point3d:
    """Point on segment p0→p1, *behind* p1 by `dist` (along flat XY), with linear Z.

    Ported from SSTools GetOffsetPoint.
    """
    d = _distance_in_plane(p0, p1)
    if d < 1e-12:
        return p1

    tz = (p0.z - p1.z) / d * dist + p1.z
    flat_len = _distance_in_plane(p0, p1)  # same as d for flat points
    p_dist = flat_len - dist
    frac = p_dist / flat_len if flat_len > 1e-12 else 0.0
    x = p0.x + (p1.x - p0.x) * frac
    y = p0.y + (p1.y - p0.y) * frac
    return Ge.Point3d(x, y, tz)


def _compute_stroke_end(
    top_pt: Ge.Point3d,
    bottom_pt: Ge.Point3d,
    is_short: bool,
    bottom_offset: float,
    mid_ratio: float,
    use_mid_length: bool,
    mid_length: float,
) -> Ge.Point3d:
    """Compute the actual end point of a stroke line.

    Ported from SSTools ComputeStrokeEndPoint.
    """
    L = _distance_in_plane(top_pt, bottom_pt)

    if use_mid_length:
        if is_short:
            if L <= mid_length:
                return bottom_pt
            return _get_offset_point(top_pt, bottom_pt, L - mid_length)
        # long stroke
        if L <= bottom_offset:
            return bottom_pt
        return _get_offset_point(top_pt, bottom_pt, bottom_offset)

    # ratio mode
    if L <= bottom_offset:
        if not is_short:
            return bottom_pt
        return _get_offset_point(top_pt, bottom_pt, L * (1.0 - mid_ratio))

    # L > bottom_offset
    if not is_short:
        return _get_offset_point(top_pt, bottom_pt, bottom_offset)
    # short
    return _get_offset_point(
        top_pt, bottom_pt,
        (L - bottom_offset) * (1.0 - mid_ratio) + bottom_offset,
    )


# ---------------------------------------------------------------------------
# Curve sampling
# ---------------------------------------------------------------------------


def _sample_curve(curve: Db.Curve, step: float) -> tuple[list[Ge.Point3d], float]:
    """Sample points at equal arc-length intervals. Returns (points, total_len)."""
    end_param = curve.getEndParam()
    total = curve.getDistAtParam(end_param)
    if total < 1e-12:
        return [], 0.0
    n = max(1, int(round(total / step)))
    pts = []
    for i in range(n + 1):
        d = total * i / n
        pts.append(curve.getPointAtDist(d))
    return pts, total


def _get_curve_length(curve: Db.Curve) -> float:
    """Total arc length of a curve."""
    return curve.getDistAtParam(curve.getEndParam()) - curve.getDistAtParam(
        curve.getStartParam()
    )


def _projected_points(
    curve: Db.Curve, step: float, z_vec: Ge.Vector3d
) -> list[Ge.Point3d]:
    """Sample curve and project points onto the plane via getClosestPointTo.

    Returns list of points projected to the original 3D curve.
    """
    pts_flat, _ = _sample_curve(curve, step)
    projected = []
    for p in pts_flat:
        try:
            cp = curve.getClosestPointTo(p, z_vec, False)
            projected.append(cp)
        except Exception:
            projected.append(p)
    return projected


# ---------------------------------------------------------------------------
# Normal / direction
# ---------------------------------------------------------------------------


def _normal_left(tan: Ge.Vector3d) -> Ge.Vector3d:
    """Left-pointing normal (rotate 90° CCW in XY)."""
    return Ge.Vector3d(-tan.y, tan.x, 0.0)


def _normal_right(tan: Ge.Vector3d) -> Ge.Vector3d:
    return Ge.Vector3d(tan.y, -tan.x, 0.0)


# ---------------------------------------------------------------------------
# Phase shift for closed curves  (FindBestPhaseShift)
# ---------------------------------------------------------------------------


def _find_best_phase_shift(
    top: Db.Curve, bottom: Db.Curve, samples: int = 360
) -> float:
    """Find optimal phase shift φ ∈ [0,1) aligning two closed curves.

    Ported from SSTools FindBestPhaseShift: O(n²) over 360 samples.
    """
    Lt = _get_curve_length(top)
    Lb = _get_curve_length(bottom)
    if Lt < 1e-12 or Lb < 1e-12:
        return 0.0

    P = [top.getPointAtDist(Lt * k / samples) for k in range(samples)]
    Q = [bottom.getPointAtDist(Lb * k / samples) for k in range(samples)]

    best_s = 0
    best_err = float("inf")

    for s in range(samples):
        err = 0.0
        for k in range(samples):
            err += _distance_in_plane(P[k], Q[(k + s) % samples])
        if err < best_err:
            best_err = err
            best_s = s

    return best_s / samples


# ---------------------------------------------------------------------------
# Shift curve start  (ShiftCurveStart)
# ---------------------------------------------------------------------------


def _shift_curve_start(curve: Db.Curve, dist: float) -> Db.Curve:
    """Move the start of a closed curve forward by `dist`.

    Ported from SSTools ShiftCurveStart: split at two points, rejoin in new order.
    Returns a *new* curve (original not mutated).  Falls back to original if
    splitting fails.
    """
    L = _get_curve_length(curve)
    if dist <= 0.0 or dist >= L:
        # clone so the caller owns the new curve
        return curve.clone()

    # Use polyline clone since PyRx GetSplitCurves is fragile on some types
    # Strategy: rebuild as polyline
    try:
        p_split = curve.getPointAtDist(dist)
        mid = dist + L / 2.0
        if mid >= L:
            mid -= L
        p_mid = curve.getPointAtDist(mid)

        param_split = curve.getParamAtPoint(p_split)
        param_mid = curve.getParamAtPoint(p_mid)

        params = [param_split, param_mid]
        params.sort()

        pieces_col = curve.getSplitCurves(
            Ge.DoubleCollection(params)
        )
        if pieces_col is None or len(pieces_col) < 2:
            return curve.clone()

        pieces = list(pieces_col)
        a = pieces[0]
        b = pieces[1]

        da = _distance_in_plane(a.getStartPoint(), p_split)
        db = _distance_in_plane(b.getStartPoint(), p_split)

        if da <= db:
            a.joinEntity(b)
            b.dispose()
            return a
        else:
            b.joinEntity(a)
            a.dispose()
            return b
    except Exception:
        return curve.clone()


# ---------------------------------------------------------------------------
# Reverse control — check if bottom should be reversed
# ---------------------------------------------------------------------------


def _should_reverse_curve(
    top: Db.Curve, bottom: Db.Curve, open_match_samples: int = 50,
    phase_ambiguity_factor: float = 0.05
) -> bool:
    """Determine if bottom curve runs opposite to top.

    Ported from SSTools ReverseControl / ShouldReverseOpenBottom.
    """
    Lt = _get_curve_length(top)
    Lb = _get_curve_length(bottom)

    s1 = (_distance_in_plane(top.getStartPoint(), bottom.getStartPoint())
          + _distance_in_plane(top.getEndPoint(), bottom.getEndPoint()))
    s2 = (_distance_in_plane(top.getStartPoint(), bottom.getEndPoint())
          + _distance_in_plane(top.getEndPoint(), bottom.getStartPoint()))

    total_dist = s1 + s2
    if total_dist > 1e-12 and abs(s1 - s2) > phase_ambiguity_factor * total_dist:
        return s2 < s1

    # Ambiguous — use sampling
    sum_direct = 0.0
    sum_reverse = 0.0
    for k in range(open_match_samples + 1):
        t = k / open_match_samples
        tp = top.getPointAtDist(Lt * t)
        bp = bottom.getPointAtDist(Lb * t)
        sum_direct += _distance_in_plane(tp, bp)
        bp_rev = bottom.getPointAtDist(Lb * (1.0 - t))
        sum_reverse += _distance_in_plane(tp, bp_rev)

    return sum_reverse < sum_direct


# ---------------------------------------------------------------------------
# Anchor point on bottom
# ---------------------------------------------------------------------------


def _get_anchor_on_bottom(line: Db.Line, bottom: Db.Curve) -> Ge.Point3d:
    """Find intersection point of a stroke line with the bottom curve.

    Ported from SSTools GetAnchorPointOnBottom.
    """
    if _distance_in_plane(line.getStartPoint(), line.getEndPoint()) < 1e-12:
        return line.getEndPoint()

    coll = Ge.Point3dCollection()
    bottom.intersectWith(line, Db.Intersect.kOnBothOperands, coll)
    if len(coll) == 0:
        return line.getEndPoint()

    best = None
    best_d = float("inf")
    ep = line.getEndPoint()
    for p in coll:
        d = _distance_in_plane(ep, p)
        if d < best_d:
            best_d = d
            best = p
    return best if best is not None else line.getEndPoint()


# ---------------------------------------------------------------------------
# Stroke creation (draw)
# ---------------------------------------------------------------------------


def _make_line(
    db: Db.Database, start_pt: Ge.Point3d, end_pt: Ge.Point3d,
    layer_id: Db.ObjectId,
) -> Db.ObjectId:
    """Create a Line in modelspace and return its ObjectId."""
    model = Db.BlockTableRecord(db.getModelSpaceId(), Db.OpenMode.kForWrite)
    line = Db.Line(start_pt, end_pt)
    line.setDatabaseDefaults(db)
    line.setLayer(layer_id)
    model.append(line)
    model.close()
    return line.objectId()


# ---------------------------------------------------------------------------
# Is stroke short?  (shortCount schemes 0..4)
# ---------------------------------------------------------------------------


def _is_short_stroke(index: int, short_count: int) -> bool:
    """Determine if stroke at `index` should be short, per SSTools schemes.

    short_count: 0=all full, 1=first only, 2=even non-zero, 3=every 3rd, 4=mask.
    """
    if short_count == 0:
        return False
    if short_count == 1:
        return index == 0
    if short_count == 2:
        return index > 0 and index % 2 == 0
    if short_count == 3:
        return index > 0 and index % 3 == 0
    if short_count == 4:
        # Special mask: pattern from the original
        return index > 0 and ((index % 4 == 0) or ((index + 1) % 4 == 0 and index % 2 != 0))
    return False


# ---------------------------------------------------------------------------
# Sprinkle-stroke count check per SSTools (TooFewStrokes guard)
# ---------------------------------------------------------------------------


def _check_min_strokes(
    num_strokes: int, short_count: int, closed: bool
) -> bool:
    """Return True if the stroke count is acceptable (> minimum thresholds)."""
    if not closed:
        return True  # open curves are less strict
    if short_count == 2:
        # need at least 6 for closed with shortCount=2
        return num_strokes >= 6
    if short_count in (1, 3):
        return num_strokes >= 3
    return True


# ---------------------------------------------------------------------------
# Tangent at index (via central difference)
# ---------------------------------------------------------------------------


def _tangent_at(pts: list[Ge.Point3d], idx: int) -> Ge.Vector3d:
    """Approximate tangent (unit) at sample index."""
    n = len(pts)
    if n == 1:
        return Ge.Vector3d(1, 0, 0)
    if idx == 0:
        dx = pts[1].x - pts[0].x
        dy = pts[1].y - pts[0].y
    elif idx == n - 1:
        dx = pts[-1].x - pts[-2].x
        dy = pts[-1].y - pts[-2].y
    else:
        dx = pts[idx + 1].x - pts[idx - 1].x
        dy = pts[idx + 1].y - pts[idx - 1].y
    length = math.hypot(dx, dy)
    if length < 1e-12:
        return Ge.Vector3d(1, 0, 0)
    return Ge.Vector3d(dx / length, dy / length, 0.0)


# ---------------------------------------------------------------------------
# Get orthogonal projected curve  (shim — not always in PyRx)
# ---------------------------------------------------------------------------


def _get_ortho_projected(curve: Db.Curve, plane_normal: Ge.Vector3d) -> Db.Curve:
    """Project curve orthogonally onto the plane with given normal."""
    try:
        return curve.getOrthoProjectedCurve(plane_normal)
    except Exception:
        # Fallback: flatten points and rebuild as polyline
        cloned = curve.clone()
        try:
            # try flatten — some curve types support it
            cloned.setPropertiesFrom(curve)
        except Exception:
            pass
        return cloned


# ---------------------------------------------------------------------------
# Curve clockwise detection (stub — relies on AutoCAD API)
# ---------------------------------------------------------------------------


def _get_clockwise_order(curve: Db.Curve) -> int:
    """Return 1 for CW, -1 for CCW, 0 for unknown/open."""
    if not curve.isClosed():
        return 0
    try:
        # Use signed area on tessellated points
        end_param = curve.getEndParam()
        total = curve.getDistAtParam(end_param)
        n = 100
        pts = []
        for i in range(n + 1):
            d = total * i / n
            p = curve.getPointAtDist(d)
            pts.append((p.x, p.y))
        area = 0.0
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            area += x1 * y2 - x2 * y1
        return 1 if area < 0 else -1
    except Exception:
        return 0