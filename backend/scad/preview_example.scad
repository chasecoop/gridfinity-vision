// Standalone preview of bin_template.scad, for manual sanity checks:
//   openscad --render -o preview.stl backend/scad/preview_example.scad
// Not used by the app — geometry.py generates its own per-job file that
// calls render_bin() the same way, with real measured values.
include <bin_template.scad>
render_bin(2, 2, 3, 15, [[8, 8], [34, 8], [34, 34], [8, 34]]);
