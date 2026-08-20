// bin_template.scad
//
// Renders a single Gridfinity bin (outer shell from gridfinity-rebuilt-openscad,
// vendored at ./gridfinity-rebuilt-openscad/) with one custom pocket cut into the
// top, shaped from an arbitrary 2D polygon.
//
// This file is not meant to be edited per-job. geometry.py generates a small
// params file per request that sets the variables below and then
// `include`s this file — that's the file actually passed to `openscad -o`.
//
// Coordinate system: cutout_points are in bin-local XY millimeters, where
// [0, 0] is the bottom-left corner of the bin's infill area (inside the
// walls). geometry.py is responsible for centering the item's silhouette
// within the infill rectangle before writing cutout_points here.

use <gridfinity-rebuilt-openscad/src/core/standard.scad>
use <gridfinity-rebuilt-openscad/src/core/gridfinity-rebuilt-utility.scad>
use <gridfinity-rebuilt-openscad/src/core/gridfinity-rebuilt-holes.scad>
use <gridfinity-rebuilt-openscad/src/core/bin.scad>

$fa = 4;
$fs = 0.25;

// ===== Defaults (overridden by the generated params file) ===== //

// Bin footprint, in 42mm grid units.
gridx = 2;
gridy = 2;

// Bin height, in 7mm height units (gridfinity "U").
gridz = 3;

// Depth of the pocket cut from the top of the bin, in mm.
pocket_depth = 15;

// Pocket outline, in bin-local infill-space mm (see coordinate note above).
// Defaults to a simple centered square so this file renders standalone.
cutout_points = [[8, 8], [34, 8], [34, 34], [8, 34]];

// ===== Implementation ===== //

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
