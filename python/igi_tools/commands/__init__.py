"""Register all IGI Tools CAD commands."""

from igi_tools.commands import align_sp92 as _align_sp92  # noqa: F401
from igi_tools.commands import check_update as _check_update  # noqa: F401
from igi_tools.commands import buffer_poly as _buffer_poly  # noqa: F401
from igi_tools.commands import fill_area as _fill_area  # noqa: F401
from igi_tools.commands import dem_tracker as _dem_tracker  # noqa: F401
from igi_tools.commands import draw_nomenclature as _draw_nomenclature  # noqa: F401
from igi_tools.commands import gzu_from_geojson as _gzu_from_geojson  # noqa: F401
from igi_tools.commands import manage_template as _manage_template  # noqa: F401
from igi_tools.commands import reload_all as _reload_all  # noqa: F401

__all__ = [
    "align_sp92",
    "check_update",
    "buffer_poly",
    "fill_area",
    "dem_tracker",
    "draw_nomenclature",
    "gzu_from_geojson",
    "manage_template",
    "reload_all",
]
