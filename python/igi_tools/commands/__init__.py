"""Register all IGI Tools CAD commands."""

from igi_tools.commands import check_update as _check_update  # noqa: F401
from igi_tools.commands import draw_nomenclature as _draw_nomenclature  # noqa: F401
from igi_tools.commands import gzu_from_geojson as _gzu_from_geojson  # noqa: F401
from igi_tools.commands import manage_template as _manage_template  # noqa: F401

__all__ = [
    "check_update",
    "draw_nomenclature",
    "gzu_from_geojson",
    "manage_template",
]
