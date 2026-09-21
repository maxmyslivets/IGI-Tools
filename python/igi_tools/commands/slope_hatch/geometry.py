"""Geometry helpers for slope hatch."""

from __future__ import annotations

import math

from pyrx import Db, Ge


_SMOOTH_ITERATIONS = 3
_SMOOTH_WEIGHT_SELF = 0.4
_SMOOTH_WEIGHT_NEIGHBOR = 0.3


def _sample_curve(curve: Db.Curve, step: float) -> tuple[list[Ge.Point3d], float]:
    """Sample points at equal arc-length intervals along a Curve.
    Returns (points_xy, total_length). Points have Z=0."""
    end_param = curve.getEndParam()
    total = curve.getDistAtParam(end_param)
    if total < 1e-12:
        return [], 0.0
    n = max(1, int(total / step))
    pts = []
    for i in range(n + 1):
        d = total * i / n
        raw = curve.getPointAtDist(d)
        pts.append(Ge.Point3d(raw.x, raw.y, 0.0))
    return pts, total


def _tessellate_curve(curve: Db.Curve, num_segments: int = 300) -> list[Ge.Point3d]:
    """Tessellate curve into many small points for segment-based intersection."""
    try:
        end_param = curve.getEndParam()
        total = curve.getDistAtParam(end_param)
        if total < 1e-12:
            return []
        pts = []
        for i in range(num_segments + 1):
            d = total * i / num_segments
            raw = curve.getPointAtDist(d)
            pts.append(Ge.Point3d(raw.x, raw.y, 0.0))
        return pts
    except Exception:
        return []


def _tangent_at(pts: list[Ge.Point3d], idx: int) -> Ge.Vector3d:
    """Approximate tangent (unit) at sample index using neighbours."""
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


def _normal(tan: Ge.Vector3d) -> Ge.Vector3d:
    """Left-pointing normal (rotate tangent 90° CCW in XY)."""
    return Ge.Vector3d(-tan.y, tan.x, 0.0)


def _segment_ray_intersection(
    origin: Ge.Point3d,
    direction: Ge.Vector3d,
    a: Ge.Point3d,
    b: Ge.Point3d,
) -> Ge.Point3d | None:
    """Intersect a ray (origin + t*direction) with segment a-b. Return point or None."""
    dx = b.x - a.x
    dy = b.y - a.y
    denom = direction.x * dy - direction.y * dx
    if abs(denom) < 1e-12:
        return None  # parallel
    t_ = ((a.x - origin.x) * dy - (a.y - origin.y) * dx) / denom
    u_ = ((a.x - origin.x) * direction.y - (a.y - origin.y) * direction.x) / denom
    if t_ < 0.0:
        return None  # behind ray
    if u_ < 0.0 or u_ > 1.0:
        return None  # outside segment
    return Ge.Point3d(origin.x + t_ * direction.x, origin.y + t_ * direction.y, 0.0)


def _project_point_on_segment(
    pt: Ge.Point3d,
    a: Ge.Point3d,
    b: Ge.Point3d,
) -> tuple[Ge.Point3d, float]:
    """Project point onto segment a-b. Return (closest_point, distance)."""
    dx = b.x - a.x
    dy = b.y - a.y
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-12:
        closest = a
    else:
        t_ = ((pt.x - a.x) * dx + (pt.y - a.y) * dy) / seg_len_sq
        t_ = max(0.0, min(1.0, t_))
        closest = Ge.Point3d(a.x + t_ * dx, a.y + t_ * dy, 0.0)
    dist = math.hypot(pt.x - closest.x, pt.y - closest.y)
    return (closest, dist)


def _arc_length_along(toe_pts: list[Ge.Point3d], pt: Ge.Point3d) -> float:
    """Estimate arc-length position of a point along a tessellated polyline."""
    best = float("inf")
    best_i = 0
    for i in range(len(toe_pts) - 1):
        a, b = toe_pts[i], toe_pts[i + 1]
        dx = b.x - a.x
        dy = b.y - a.y
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq < 1e-12:
            continue
        t_ = ((pt.x - a.x) * dx + (pt.y - a.y) * dy) / seg_len_sq
        if t_ < 0.0 or t_ > 1.0:
            continue
        proj_x = a.x + t_ * dx
        proj_y = a.y + t_ * dy
        d = math.hypot(pt.x - proj_x, pt.y - proj_y)
        if d < best:
            best = d
            best_i = i
    cum = 0.0
    for i in range(best_i):
        dx = toe_pts[i + 1].x - toe_pts[i].x
        dy = toe_pts[i + 1].y - toe_pts[i].y
        cum += math.hypot(dx, dy)
    a, b = toe_pts[best_i], toe_pts[best_i + 1]
    dx = b.x - a.x
    dy = b.y - a.y
    seg_len = math.hypot(dx, dy)
    if seg_len > 1e-12:
        t_ = ((pt.x - a.x) * dx + (pt.y - a.y) * dy) / (seg_len * seg_len)
        t_ = max(0.0, min(1.0, t_))
        cum += seg_len * t_
    return cum


def _find_brink_normal_dir(
    brink_pt: Ge.Point3d, toe_curve: Db.Curve, tan: Ge.Vector3d
) -> Ge.Vector3d:
    """Determine which normal direction (left or right) points toward the toe.
    Use getClosestPointTo to find nearest toe point, then check dot product."""
    nrm_left = _normal(tan)
    nrm_right = Ge.Vector3d(-nrm_left.x, -nrm_left.y, 0.0)
    try:
        closest = toe_curve.getClosestPointTo(brink_pt, False)
        to_toe = Ge.Vector3d(closest.x - brink_pt.x, closest.y - brink_pt.y, 0.0)
        to_len = to_toe.length()
        if to_len < 1e-12:
            return nrm_left
        to_toe = to_toe / to_len
        return nrm_left if nrm_left.dotProduct(to_toe) > 0 else nrm_right
    except Exception:
        return nrm_left


def _find_toe_point(
    brink_pt: Ge.Point3d,
    normal_dir: Ge.Vector3d,
    toe_pts: list[Ge.Point3d],
    toe_curve: Db.Curve,
    prev_toe_pt: Ge.Point3d | None,
) -> Ge.Point3d | None:
    """Find hatch-line end point on toe.
    1. Ray intersection with tessellated toe segments along normal_dir.
    2. Fallback: getClosestPointTo.
    3. ANTI-CROSSING: clamp if arc-length regressed.
    """
    if len(toe_pts) < 2:
        return None

    # Step 1: ray intersection along normal_dir (forward only)
    best_pt: Ge.Point3d | None = None
    best_dist = float("inf")
    for i in range(len(toe_pts) - 1):
        a, b = toe_pts[i], toe_pts[i + 1]
        pt = _segment_ray_intersection(brink_pt, normal_dir, a, b)
        if pt is not None:
            d = math.hypot(pt.x - brink_pt.x, pt.y - brink_pt.y)
            if d < best_dist:
                best_dist = d
                best_pt = pt

    ray_hit = best_pt is not None

    # Step 2: fallback to closest point on toe curve
    if best_pt is None:
        try:
            raw = toe_curve.getClosestPointTo(brink_pt, False)
            best_pt = Ge.Point3d(raw.x, raw.y, 0.0)
        except Exception:
            return None

    if best_pt is None:
        return None

    # Step 3: ANTI-CROSSING — only when ray-hit and prev point exists
    if prev_toe_pt is not None and ray_hit:
        try:
            pos = toe_curve.getDistAtParam(toe_curve.getParamAtPoint(best_pt))
            prev_pos = toe_curve.getDistAtParam(
                toe_curve.getParamAtPoint(prev_toe_pt)
            )
            if pos < prev_pos:
                raw = toe_curve.getClosestPointTo(brink_pt, False)
                best_pt = Ge.Point3d(raw.x, raw.y, 0.0)
        except Exception:
            pass

    return best_pt


def _redistribute_toe_points(
    raw_pairs: list[tuple[Ge.Point3d, Ge.Point3d]],
    toe_curve: Db.Curve,
    toe_pts: list[Ge.Point3d],
) -> list[tuple[Ge.Point3d, Ge.Point3d]]:
    """Smooth segment DIRECTION ANGLES (not toe positions) via neighbour
    blending of unit vectors, then find new toe points by ray intersection
    along the smoothed direction with the toe curve.
    Prevents crossing and produces a true gradient of directions.
    """
    n = len(raw_pairs)
    if n < 3:
        return raw_pairs

    # 1. Unit direction vectors (brink -> toe)
    ux: list[float] = []
    uy: list[float] = []
    for brink_pt, toe_pt in raw_pairs:
        dx = toe_pt.x - brink_pt.x
        dy = toe_pt.y - brink_pt.y
        length = math.hypot(dx, dy)
        if length < 1e-12:
            ux.append(1.0)
            uy.append(0.0)
        else:
            ux.append(dx / length)
            uy.append(dy / length)

    # 2. Smooth direction vectors (component-wise)
    for _ in range(_SMOOTH_ITERATIONS):
        nx = [ux[0]]
        ny = [uy[0]]
        for i in range(1, n - 1):
            nx.append(
                _SMOOTH_WEIGHT_SELF * ux[i]
                + _SMOOTH_WEIGHT_NEIGHBOR * ux[i - 1]
                + _SMOOTH_WEIGHT_NEIGHBOR * ux[i + 1]
            )
            ny.append(
                _SMOOTH_WEIGHT_SELF * uy[i]
                + _SMOOTH_WEIGHT_NEIGHBOR * uy[i - 1]
                + _SMOOTH_WEIGHT_NEIGHBOR * uy[i + 1]
            )
        nx.append(ux[-1])
        ny.append(uy[-1])
        ux, uy = nx, ny

    # 3. Re-normalise smoothed vectors
    smooth_dir: list[Ge.Vector3d] = []
    for x, y in zip(ux, uy):
        length = math.hypot(x, y)
        if length < 1e-12:
            smooth_dir.append(Ge.Vector3d(1.0, 0.0, 0.0))
        else:
            smooth_dir.append(Ge.Vector3d(x / length, y / length, 0.0))

    # 4. Ray intersection along smoothed direction  →  new toe point
    adjusted: list[tuple[Ge.Point3d, Ge.Point3d]] = []
    for i, (brink_pt, raw_toe_pt) in enumerate(raw_pairs):
        dir_vec = smooth_dir[i]
        best_pt: Ge.Point3d | None = None
        best_dist = float("inf")
        for j in range(len(toe_pts) - 1):
            a, b = toe_pts[j], toe_pts[j + 1]
            pt = _segment_ray_intersection(brink_pt, dir_vec, a, b)
            if pt is not None:
                d = math.hypot(pt.x - brink_pt.x, pt.y - brink_pt.y)
                if d < best_dist:
                    best_dist = d
                    best_pt = pt
        if best_pt is not None:
            adjusted.append((brink_pt, best_pt))
        else:
            adjusted.append((brink_pt, raw_toe_pt))

    return adjusted
