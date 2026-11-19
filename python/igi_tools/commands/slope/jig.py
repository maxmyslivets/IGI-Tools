"""Interactive Jig for slope editing."""

from __future__ import annotations

from typing import Any

import wx
from pyrx import Db, Ed, Ge, Gi

from igi_tools.commands.slope.geometry import _compute_stroke_end


class SlopeEditJig(Ed.DrawJig):
    """DrawJig for interactive editing of slope strokes.

    Behaviour:
      - Dragged bottom endpoint moves along the bottom curve.
      - Neighbouring strokes within capture_radius move via
        **linear interpolation** between range bounds, guaranteeing
        monotonic ordering (no crossings).
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
        radius_dlg: Any = None,
        orig_end_pts: list[Ge.Point3d] | None = None,
    ) -> None:
        super().__init__()
        self._top_curve = top_curve
        self._bot_curve = bot_curve
        self._stroke_top_pts = stroke_top_pts
        self._orig_bottom_dists = orig_bottom_dists
        self._orig_end_pts = orig_end_pts or list(stroke_top_pts)
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
        self._radius_dlg = radius_dlg

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
            f"Откос: двигайте низ штриха | слайдер — радиус"
        )
        self.setKeywordList("+R -R")

    # ── Jig overrides ──

    def sampler(self) -> Ed.DragStatus:
        """Acquire cursor point or keyword."""
        # Process wx events so modeless dialog updates reach us
        if self._radius_dlg is not None:
            wx.Yield()

        status, pt = self.acquirePoint(self._base_pt)

        if status == Ed.DragStatus.kKW1:  # +R
            self._cursor_pt = pt
            self._capture_radius = min(self._capture_radius + 1, self._total_strokes // 2)
            self.setDispPrompt(
                f"Откос: двигайте низ штриха | +R -R (радиус: {self._capture_radius})"
            )
            return Ed.DragStatus.kNormal  # trigger update/redraw

        if status == Ed.DragStatus.kKW2:  # -R
            self._cursor_pt = pt
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
        """Compute new bottom end positions.

        Uses linear interpolation between range bounds (not falloff)
        to guarantee monotonic ordering of bottom distances.
        """
        # Read radius from modeless dialog if present
        if self._radius_dlg is not None and self._radius_dlg.IsShown():
            self._capture_radius = self._radius_dlg.radius

        if self._cursor_pt is None:
            return False

        try:
            # Project cursor onto bottom curve
            closest = self._bot_curve.getClosestPointTo(self._cursor_pt, False)
            cursor_dist = self._bot_curve.getDistAtPoint(closest)
        except Exception:
            return False

        # Range: inclusive bounds of affected strokes
        left_idx = max(0, self._sel_idx - self._capture_radius)
        right_idx = min(self._total_strokes - 1, self._sel_idx + self._capture_radius)

        # Clamp cursor_dist to stay within original range — prevents extrapolation
        lo = min(self._orig_bottom_dists[left_idx], self._orig_bottom_dists[right_idx])
        hi = max(self._orig_bottom_dists[left_idx], self._orig_bottom_dists[right_idx])
        cursor_dist = max(lo, min(cursor_dist, hi))

        new_end_pts: list[Ge.Point3d] = []
        new_bottom_dists: list[float] = []

        for i in range(self._total_strokes):
            orig_d = self._orig_bottom_dists[i]

            if i < left_idx or i > right_idx:
                # Unaffected — keep original end point exactly as-is
                new_end_pts.append(self._orig_end_pts[i])
                new_bottom_dists.append(orig_d)
                continue

            if i == self._sel_idx:
                new_d = cursor_dist
            elif i < self._sel_idx:
                # Interpolate between orig_d[left_idx] and cursor_dist
                frac = (i - left_idx) / (self._sel_idx - left_idx)
                new_d = self._orig_bottom_dists[left_idx] + (cursor_dist - self._orig_bottom_dists[left_idx]) * frac
            else:
                # Interpolate between cursor_dist and orig_d[right_idx]
                frac = (i - self._sel_idx) / (right_idx - self._sel_idx)
                new_d = cursor_dist + (self._orig_bottom_dists[right_idx] - cursor_dist) * frac

            new_bottom_dists.append(new_d)

            # Clamp to valid curve range
            new_d = max(0.0, min(new_d, self._bot_length - 1e-10))

            try:
                bp = self._bot_curve.getPointAtDist(new_d)
            except Exception:
                bp = self._stroke_top_pts[i]  # fallback

            # Compute stroke end (with bottom offset, short stroke, etc.)
            is_short = self._is_short_stroke(i)
            end_pt = self._compute_stroke_end(self._stroke_top_pts[i], bp, is_short)
            new_end_pts.append(end_pt)

        self._new_end_pts = new_end_pts
        self._new_bottom_dists = new_bottom_dists
        return True

    def worldDraw(self, wd: Gi.WorldDraw) -> bool:
        """Draw preview strokes."""
        traits = wd.subEntityTraits()
        geo = wd.geometry()
        normal = self._plane_normal

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
        """Compute actual end point of a stroke (delegates to geometry._compute_stroke_end)."""
        return _compute_stroke_end(
            top_pt, bottom_pt, is_short,
            self._bottom_offset, self._mid_ratio,
            self._use_mid_length, self._mid_length,
        )



