"""Interactive Jig for slope editing."""

from __future__ import annotations

import math

from pyrx import Db, Ed, Ge, Gi


class SlopeEditJig(Ed.DrawJig):
    """DrawJig for interactive editing of slope strokes.

    Behaviour:
      - Dragged bottom endpoint moves along the bottom curve.
      - Neighbouring strokes within capture_radius move with falloff.
      - Keywords: +R / -R to adjust capture_radius.
    """

    def __init__(
        self,
        top_curve: Db.Curve,
        bot_curve: Db.Curve,
        stroke_top_pts: list[Ge.Point3d],
        orig_bottom_dists: list[float],
        sel_idx: int,
        bot_length: float,
        total_strokes: int,
        step: float,
        bottom_offset: float,
        short_count: int,
        use_mid_length: bool,
        mid_ratio: float,
        mid_length: float,
        plane_normal: Ge.Vector3d,
    ) -> None:
        super().__init__()
        self._top_curve = top_curve
        self._bot_curve = bot_curve
        self._stroke_top_pts = stroke_top_pts
        self._orig_bottom_dists = orig_bottom_dists
        self._sel_idx = sel_idx
        self._bot_length = bot_length
        self._total_strokes = total_strokes
        self._step = step
        self._bottom_offset = bottom_offset
        self._short_count = short_count
        self._use_mid_length = use_mid_length
        self._mid_ratio = mid_ratio
        self._mid_length = mid_length
        self._plane_normal = plane_normal

        # Editable state
        self._cursor_pt: Ge.Point3d | None = None
        self._capture_radius: int = 3  # neighbours on each side (adjustable)
        self._new_end_pts: list[Ge.Point3d] = []  # set during update()
        self._new_bottom_dists: list[float] = list(orig_bottom_dists)  # updated during drag
        self._final_end_pts: list[Ge.Point3d] = list(stroke_top_pts)  # fallback copy

        # Base point for acquirePoint – the selected stroke's original bottom
        try:
            base = self._bot_curve.getPointAtDist(self._orig_bottom_dists[sel_idx])
        except Exception:
            base = Ge.Point3d(0, 0, 0)
        self._base_pt = base

        self.setDispPrompt(
            f"Откос: двигайте низ штриха | +R -R (радиус: {self._capture_radius})"
        )
        self.setKeywordList("+R -R")

    # ── Jig overrides ──

    def sampler(self) -> Ed.DragStatus:
        """Acquire cursor point or keyword."""
        status, pt = self.acquirePoint(self._base_pt)

        if status == Ed.DragStatus.kKW1:  # +R
            self._capture_radius = min(self._capture_radius + 1, self._total_strokes // 2)
            self.setDispPrompt(
                f"Откос: двигайте низ штриха | +R -R (радиус: {self._capture_radius})"
            )
            return Ed.DragStatus.kNormal  # trigger update/redraw

        if status == Ed.DragStatus.kKW2:  # -R
            self._capture_radius = max(self._capture_radius - 1, 0)
            self.setDispPrompt(
                f"Откос: двигайте низ штриха | +R -R (радиус: {self._capture_radius})"
            )
            return Ed.DragStatus.kNormal

        if status == Ed.DragStatus.kNormal:
            self._cursor_pt = pt
        else:
            self._cursor_pt = None
        return status

    def update(self) -> bool:
        """Compute new bottom end positions for all strokes."""
        if self._cursor_pt is None:
            return False

        try:
            # Project cursor onto bottom curve
            closest = self._bot_curve.getClosestPointTo(self._cursor_pt, False)
            cursor_dist = self._bot_curve.getDistAtPoint(closest)
        except Exception:
            return False

        sel_orig = self._orig_bottom_dists[self._sel_idx]
        delta = cursor_dist - sel_orig

        new_end_pts: list[Ge.Point3d] = []
        new_bottom_dists: list[float] = []

        for i in range(self._total_strokes):
            top_pt = self._stroke_top_pts[i]
            orig_d = self._orig_bottom_dists[i]
            dist_i = abs(i - self._sel_idx)

            if dist_i == 0:
                new_d = cursor_dist
            elif dist_i <= self._capture_radius:
                falloff = 1.0 - dist_i / (self._capture_radius + 1.0)
                new_d = orig_d + delta * falloff
            else:
                new_d = orig_d

            new_bottom_dists.append(new_d)

            # Clamp to valid range
            new_d = max(0.0, min(new_d, self._bot_length - 1e-10))

            try:
                bp = self._bot_curve.getPointAtDist(new_d)
            except Exception:
                bp = top_pt  # fallback

            # Compute stroke end (with bottom offset, short stroke, etc.)
            is_short = self._is_short_stroke(i)
            end_pt = self._compute_stroke_end(top_pt, bp, is_short)
            new_end_pts.append(end_pt)

        self._new_end_pts = new_end_pts
        self._new_bottom_dists = new_bottom_dists
        return True

    def worldDraw(self, wd: Gi.WorldDraw) -> bool:
        """Draw preview strokes."""
        traits = wd.subEntityTraits()
        geo = wd.geometry()
        normal = Ge.Vector3d.kZAxis  # or self._plane_normal

        for i in range(self._total_strokes):
            top_pt = self._stroke_top_pts[i]
            end_pt = self._new_end_pts[i] if i < len(self._new_end_pts) else top_pt

            dist_i = abs(i - self._sel_idx)

            if dist_i == 0:
                traits.setColor(3)  # green – selected
            elif dist_i <= self._capture_radius:
                traits.setColor(2)  # yellow – captured neighbours
            else:
                traits.setColor(8)  # gray – unaffected

            geo.polyline([top_pt, end_pt], normal)

        return True

    # ── Helpers ──

    def _is_short_stroke(self, index: int) -> bool:
        """Mirrors geometry._is_short_stroke."""
        sc = self._short_count
        if sc == 0:
            return False
        if sc == 1:
            return index == 0
        if sc == 2:
            return index > 0 and index % 2 == 0
        if sc == 3:
            return index > 0 and index % 3 == 0
        # sc == 4 — special mask; treat as every 2nd for now
        return index > 0 and index % 2 == 0

    def get_new_end_pts(self) -> list[Ge.Point3d]:
        return list(self._new_end_pts)

    def get_new_bottom_dists(self) -> list[float]:
        return list(self._new_bottom_dists)

    def _compute_stroke_end(
        self,
        top_pt: Ge.Point3d,
        bottom_pt: Ge.Point3d,
        is_short: bool,
    ) -> Ge.Point3d:
        """Compute actual end point of a stroke (with bottom_offset, short stroke)."""
        return _calc_stroke_end(
            top_pt, bottom_pt, is_short,
            self._bottom_offset, self._mid_ratio,
            self._use_mid_length, self._mid_length,
        )


def _calc_stroke_end(
    top_pt: Ge.Point3d,
    bottom_pt: Ge.Point3d,
    is_short: bool,
    bottom_offset: float,
    mid_ratio: float,
    use_mid_length: bool,
    mid_length: float,
) -> Ge.Point3d:
    """Pure-function version of compute_stroke_end (no Db dependency)."""
    # Flat distance
    dx = bottom_pt.x - top_pt.x
    dy = bottom_pt.y - top_pt.y
    L = math.sqrt(dx * dx + dy * dy)

    if L < 1e-12:
        return bottom_pt

    # Z-interpolation factor
    t = 1.0  # default: go all the way to bottom

    if use_mid_length:
        if is_short:
            if L <= mid_length:
                t = 1.0
            else:
                t = (L - mid_length) / L
        else:
            if L <= bottom_offset:
                t = 1.0
            else:
                t = (L - bottom_offset) / L
    else:
        if L <= bottom_offset:
            if not is_short:
                t = 1.0
            else:
                t = (1.0 - mid_ratio)
        else:
            if not is_short:
                t = (L - bottom_offset) / L
            else:
                remaining = L - bottom_offset
                if remaining < 1e-12:
                    t = 1.0
                else:
                    short_part = remaining * (1.0 - mid_ratio)
                    t = (bottom_offset + short_part) / L

    t = max(0.0, min(1.0, t))

    end_x = top_pt.x + dx * t
    end_y = top_pt.y + dy * t
    end_z = top_pt.z + (bottom_pt.z - top_pt.z) * t

    return Ge.Point3d(end_x, end_y, end_z)