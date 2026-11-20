"""Interactive Jig for slope editing."""

from __future__ import annotations

from pyrx import Db, Ed, Ge, Gi

from igi_tools.commands.slope.geometry import _compute_stroke_end


class SlopeEditJig(Ed.DrawJig):
    """DrawJig for interactive editing of slope strokes.

    Behaviour:
      - Dragged bottom endpoint moves along the bottom curve.
      - Only strokes within `radius` of the selected index are affected,
        with falloff (power^) from 1.0 (selected) to 0.0 (edge of radius).
      - Strokes outside the radius stay unchanged.
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
        radius_dlg: object | None = None,
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
        self._radius_dlg = radius_dlg

        # ── Compute "мысленные" дистанции для коротких штрихов ──
        # Для длинных orig_bottom_dists — это проекция реального end_pt на bot_curve,
        # а end_pt лежит на самом контуре (длинный штрих доходит).
        # Для коротких orig_bottom_dists — проекция укороченного конца, которая
        # НЕ совпадает с точкой "мысленного" пересечения с контуром.
        # Мы храним orig_bottom_dists как есть (для falloff continuity),
        # а для коротких дополнительно вычисляем extended_dists — дистанции
        # "мысленных" точек пересечения с bot_curve.
        #
        # Для восстановления мысленной дистанции интерполируем от соседних
        # ДЛИННЫХ штрихов (которые реально доходят до контура).
        self._extended_bottom_dists: list[float] = list(orig_bottom_dists)
        for i in range(total_strokes):
            if self._is_short_stroke(i):
                # Найти ближайший длинный штрих слева
                left_idx = i - 1
                while left_idx >= 0 and self._is_short_stroke(left_idx):
                    left_idx -= 1
                # Найти ближайший длинный штрих справа
                right_idx = i + 1
                while right_idx < total_strokes and self._is_short_stroke(right_idx):
                    right_idx += 1

                if left_idx >= 0 and right_idx < total_strokes:
                    # Интерполяция между двумя длинными
                    frac = (i - left_idx) / (right_idx - left_idx)
                    ext_d = orig_bottom_dists[left_idx] + frac * (
                        orig_bottom_dists[right_idx] - orig_bottom_dists[left_idx]
                    )
                    self._extended_bottom_dists[i] = ext_d
                elif left_idx >= 0:
                    # Только слева — экстраполяция
                    self._extended_bottom_dists[i] = orig_bottom_dists[left_idx]
                elif right_idx < total_strokes:
                    # Только справа — экстраполяция
                    self._extended_bottom_dists[i] = orig_bottom_dists[right_idx]

        # Editable state
        self._cursor_pt: Ge.Point3d | None = None
        self._new_end_pts: list[Ge.Point3d] = []  # set during update()
        self._new_bottom_dists: list[float] = list(orig_bottom_dists)  # updated during drag
        self._new_extended_dists: list[float] = list(self._extended_bottom_dists)
        self._final_end_pts: list[Ge.Point3d] = list(stroke_top_pts)  # fallback copy

        # Base point for acquirePoint – the selected stroke's original bottom
        # Используем мысленную дистанцию (extended), чтобы база была на контуре
        try:
            base = self._bot_curve.getPointAtDist(self._extended_bottom_dists[sel_idx])
        except Exception:
            base = Ge.Point3d(0, 0, 0)
        self._base_pt = base

        self.setDispPrompt(
            "Откос: двигайте низ штриха"
        )

    def _get_radius(self) -> int:
        """Get current capture radius from the modeless dialog."""
        if self._radius_dlg is not None:
            try:
                return int(self._radius_dlg.radius)
            except Exception:
                pass
        return max(self._sel_idx, self._total_strokes - 1 - self._sel_idx)

    def _get_power(self) -> float:
        """Fixed linear falloff: power = 1.0"""
        return 1.0

    # ── Jig overrides ──

    def sampler(self) -> Ed.DragStatus:
        """Acquire cursor point."""
        status, pt = self.acquirePoint(self._base_pt)

        if status == Ed.DragStatus.kNormal:
            self._cursor_pt = pt
        else:
            self._cursor_pt = None
        return status

    def update(self) -> bool:
        """Compute new bottom end positions.

        Falloff within radius:
          - Only strokes with |i - sel_idx| <= radius are affected.
          - t_rel = |i - sel_idx| / radius   (0..1 within radius)
          - fade = (1.0 - t_rel) ** 1.0  (linear falloff)
          - At radius boundary: fade = 0 (no displacement).
          - Outside radius: unchanged.
        """
        if self._cursor_pt is None:
            return False

        try:
            # Project cursor onto bottom curve
            closest = self._bot_curve.getClosestPointTo(self._cursor_pt, False)
            cursor_dist = self._bot_curve.getDistAtPoint(closest)
        except Exception:
            return False

        # Clamp cursor_dist — используем общий диапазон мысленных дистанций
        # (prevents strokes from crossing each other during editing)
        lo = min(self._extended_bottom_dists)
        hi = max(self._extended_bottom_dists)
        cursor_dist = max(lo, min(cursor_dist, hi))

        # Displacement of the selected stroke (delta from original)
        sel_orig = self._extended_bottom_dists[self._sel_idx]
        delta = cursor_dist - sel_orig

        total = self._total_strokes
        radius = self._get_radius()
        power = self._get_power()

        new_end_pts: list[Ge.Point3d] = []
        new_bottom_dists: list[float] = []
        new_extended_dists: list[float] = []

        for i in range(total):
            is_short = self._is_short_stroke(i)
            dist = abs(i - self._sel_idx)

            # Fade calculation: 1.0 at selected, 0.0 at radius boundary
            if dist <= radius:
                if i == self._sel_idx:
                    fade = 1.0
                else:
                    t_rel = dist / radius if radius > 0 else 1.0
                    fade = 1.0 - t_rel  # linear falloff
            else:
                fade = 0.0

            if is_short:
                ext_orig = self._extended_bottom_dists[i]
                new_ext = ext_orig + delta * fade
                new_ext = max(0.0, min(new_ext, self._bot_length - 1e-10))
                new_extended_dists.append(new_ext)
                try:
                    bp = self._bot_curve.getPointAtDist(new_ext)
                except Exception:
                    bp = self._stroke_top_pts[i]
                new_bottom_dists.append(new_ext)
            else:
                orig_d = self._orig_bottom_dists[i]
                new_d = orig_d + delta * fade
                new_d = max(0.0, min(new_d, self._bot_length - 1e-10))
                new_bottom_dists.append(new_d)
                new_extended_dists.append(new_d)
                try:
                    bp = self._bot_curve.getPointAtDist(new_d)
                except Exception:
                    bp = self._stroke_top_pts[i]

            end_pt = self._compute_stroke_end(self._stroke_top_pts[i], bp, is_short)
            new_end_pts.append(end_pt)

        self._new_end_pts = new_end_pts
        self._new_bottom_dists = new_bottom_dists
        self._new_extended_dists = new_extended_dists
        return True

    def worldDraw(self, wd: Gi.WorldDraw) -> bool:
        """Draw preview strokes.

        - Green: selected stroke.
        - Yellow: affected neighbours (within radius).
        - Gray: outside radius (unchanged).
        """
        traits = wd.subEntityTraits()
        geo = wd.geometry()
        normal = self._plane_normal
        radius = self._get_radius()

        for i in range(self._total_strokes):
            top_pt = self._stroke_top_pts[i]
            end_pt = self._new_end_pts[i] if i < len(self._new_end_pts) else top_pt

            dist = abs(i - self._sel_idx)
            if i == self._sel_idx:
                traits.setColor(3)  # green – selected
            elif dist <= radius:
                traits.setColor(2)  # yellow – affected neighbours
            else:
                traits.setColor(8)  # grey – outside radius

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



