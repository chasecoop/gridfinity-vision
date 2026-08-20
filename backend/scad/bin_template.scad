// bin_template.scad
//
// Renders a single Gridfinity bin (outer shell from gridfinity-rebuilt-openscad,
// vendored at ./gridfinity-rebuilt-openscad/) with one custom pocket cut into the
// top, shaped from an arbitrary 2D polygon.
//
// This file is not meant to be edited per-job. geometry.py generates a small
// params file per request that `include`s this file and then calls
// render_bin(...) with explicit arguments — deliberately NOT global variable
// assignment. OpenSCAD's variable scoping is "last assignment in the merged
// token stream wins", regardless of include order, so passing values as
// module arguments instead of same-named globals avoids a real footgun
// where a placeholder default here could silently shadow a caller's value.
//
// Coordinate system: cutout_points are in bin-local XY millimeters, where
// [0, 0] is the bottom-left corner of the bin's infill area (inside the
// walls). geometry.py is responsible for centering the item's silhouette
// within the infill rectangle before computing cutout_points.

use <gridfinity-rebuilt-openscad/src/core/standard.scad>
use <gridfinity-rebuilt-openscad/src/core/gridfinity-rebuilt-utility.scad>
use <gridfinity-rebuilt-openscad/src/core/gridfinity-rebuilt-holes.scad>
use <gridfinity-rebuilt-openscad/src/core/bin.scad>

$fa = 4;
$fs = 0.25;

// gridx, gridy: bin footprint in 42mm grid units.
// gridz: bin height in 7mm height units (gridfinity "U").
// pocket_depth: depth of the pocket cut from the top of the bin, in mm.
// cutout_points: pocket outline, in bin-local infill-space mm (see above).
module render_bin(gridx, gridy, gridz, pocket_depth, cutout_points) {
    hole_options = bundle_hole_options(magnet_hole = true, screw_hole = true);

    bin1 = new_bin(
        grid_size = [gridx, gridy],
        height_mm = fromGridfinityUnits(gridz),
        hole_options = hole_options
    );

    bin_render(bin1) {
        translate([0, 0, -pocket_depth])
            linear_extrude(pocket_depth)
                polygon(points = cutout_points);
    }
}

// This file defines render_bin() only — no top-level geometry — so
// `include`-ing it can never shadow a caller's values (see note above).
// For a standalone preview, use backend/scad/preview_example.scad.
