"""Turns a manifest (silhouette polygon + height + bin params) into a
rendered STL, by generating a small per-job .scad params file and shelling
out to the headless `openscad` CLI against backend/scad/bin_template.scad.

Mirrors a few constants from the vendored gridfinity-rebuilt-openscad
(backend/scad/gridfinity-rebuilt-openscad/src/core/standard.scad) so the
auto-sizing math lines up with what OpenSCAD will actually build:
    BASE_HEIGHT = 7, STACKING_LIP_SUPPORT_HEIGHT = 1.2, d_wall = 0.95
If that vendored submodule is ever updated and those constants change,
update them here too.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

from shapely.geometry import Polygon

from backend.models import BinManifest
from backend.storage import OUTPUT_DIR, PROJECT_ROOT

SCAD_DIR = PROJECT_ROOT / "backend" / "scad"
BIN_TEMPLATE = SCAD_DIR / "bin_template.scad"

GRID_UNIT_MM = 42.0
HEIGHT_UNIT_MM = 7.0
D_WALL_MM = 1.2  # empirical per-side infill inset (see bin_get_infill_size_mm, not just standard.scad's d_wall)
BASE_HEIGHT_MM = 7.0  # mirrors standard.scad BASE_HEIGHT
STACKING_LIP_SUPPORT_MM = 1.2  # mirrors standard.scad STACKING_LIP_SUPPORT_HEIGHT
MIN_FLOOR_MM = 3.0  # solid material left under the pocket, for print strength


class GeometryError(Exception):
    pass


def _buffered_polygon(manifest: BinManifest) -> Polygon:
    points = [(p.x, p.y) for p in manifest.silhouette_polygon]
    if len(points) < 3:
        raise GeometryError("Silhouette needs at least 3 points.")
    poly = Polygon(points)
    if not poly.is_valid:
        poly = poly.buffer(0)  # common fix for self-intersecting auto-detected contours
    buffered = poly.buffer(manifest.clearance_mm, join_style="mitre")
    # Re-simplify after buffering — mitre joins can add points at sharp corners.
    return buffered.simplify(0.2, preserve_topology=True)


def _infill_mm(grid_units: int) -> float:
    return grid_units * GRID_UNIT_MM - 2 * D_WALL_MM


def compute_bin_params(manifest: BinManifest) -> dict:
    """Auto-sizes the bin footprint and height from the (buffered)
    silhouette and measured item height. Returns values meant to be shown
    to the user as editable defaults, not applied silently.
    """
    buffered = _buffered_polygon(manifest)
    min_x, min_y, max_x, max_y = buffered.bounds
    width_mm = max_x - min_x
    depth_mm = max_y - min_y

    grid_x = max(1, math.ceil((width_mm + 2 * D_WALL_MM) / GRID_UNIT_MM))
    grid_y = max(1, math.ceil((depth_mm + 2 * D_WALL_MM) / GRID_UNIT_MM))

    pocket_depth = (manifest.height_mm or 0) + manifest.clearance_mm
    needed_height_mm = pocket_depth + BASE_HEIGHT_MM + STACKING_LIP_SUPPORT_MM + MIN_FLOOR_MM
    bin_height_units = max(2, math.ceil(needed_height_mm / HEIGHT_UNIT_MM))

    return {
        "grid_x": grid_x,
        "grid_y": grid_y,
        "bin_height_units": bin_height_units,
    }


def _format_points(points) -> str:
    return "[" + ",".join(f"[{x:.3f},{y:.3f}]" for x, y in points) + "]"


def _write_params_file(manifest: BinManifest) -> Path:
    buffered = _buffered_polygon(manifest)
    min_x, min_y, max_x, max_y = buffered.bounds

    # bin_render()'s children are evaluated with [0, 0] at the CENTER of the
    # infill (confirmed empirically — it is not documented and not the
    # bottom-left corner one might assume from the "grid [0,0] = bottom left
    # corner" comment in gridfinity-rebuilt-bins.scad, which refers to
    # bin_translate()'s grid-index space, a different coordinate system).
    # So centering the pocket is just centering the polygon on its own
    # bounding-box center.
    offset_x = -(min_x + max_x) / 2
    offset_y = -(min_y + max_y) / 2

    centered_points = [(x + offset_x, y + offset_y) for x, y in buffered.exterior.coords]

    pocket_depth = (manifest.height_mm or 0) + manifest.clearance_mm
    fill_height = manifest.bin_height_units * HEIGHT_UNIT_MM - BASE_HEIGHT_MM - STACKING_LIP_SUPPORT_MM
    pocket_depth = min(pocket_depth, max(fill_height - 0.5, 0.5))  # never cut through the floor

    # Pass values as explicit render_bin() arguments, not global variable
    # assignment — see the note at the top of bin_template.scad for why.
    params_path = OUTPUT_DIR / f"{manifest.id}.scad"
    params_path.write_text(
        f'include <{BIN_TEMPLATE}>\n'
        f"render_bin({manifest.grid_x}, {manifest.grid_y}, {manifest.bin_height_units}, "
        f"{pocket_depth:.3f}, {_format_points(centered_points)});\n"
    )
    return params_path


def render_stl(manifest: BinManifest) -> Path:
    if manifest.grid_x is None or manifest.grid_y is None or manifest.bin_height_units is None:
        raise GeometryError("Bin params must be set before rendering (call compute_bin_params first).")

    params_path = _write_params_file(manifest)
    stl_path = OUTPUT_DIR / f"{manifest.id}.stl"

    result = subprocess.run(
        ["openscad", "-o", str(stl_path), str(params_path)],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0 or not stl_path.exists():
        raise GeometryError(f"OpenSCAD render failed:\n{result.stderr}")

    return stl_path
