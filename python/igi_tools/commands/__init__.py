"""Register all IGI Tools CAD commands."""

from igi_tools.commands import circles_on_vertices as _circles_on_vertices  # noqa: F401
from igi_tools.commands import draw_nomenclature as _draw_nomenclature  # noqa: F401
from igi_tools.commands import gzu_from_geojson as _gzu_from_geojson  # noqa: F401

__all__ = ["circles_on_vertices", "draw_nomenclature", "gzu_from_geojson"]
