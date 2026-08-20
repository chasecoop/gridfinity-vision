# Gridfinity Vision

Photograph an item from directly above and from the side, and get back a
[Gridfinity](https://gridfinity.xyz/specification/)-spec STL sized to the
nearest 42mm grid units, with a pocket cut to the item's actual silhouette
and height — ready to open in Bambu Studio.

This is **not** photogrammetry / 3D reconstruction. A Gridfinity pocket is a
straight extrusion of a 2D outline, so the pipeline only needs: real-world
scale (from a printed calibration marker in each photo), the item's outline
from directly above, and its height from the side. All classical CV, no
depth models or multi-view reconstruction — see the project plan for why
that's enough.

The generated bin's shell (walls, stacking lip, magnet holes) comes from
the community-standard [gridfinity-rebuilt-openscad](https://github.com/kennetek/gridfinity-rebuilt-openscad),
vendored as a submodule, so every bin this produces is dimensionally
consistent with bins from other Gridfinity generators.

## Setup

```bash
git clone --recurse-submodules <this repo>
cd gridfinity-vision
brew install --cask openscad@snapshot   # headless CLI renderer — the regular
                                         # `openscad` cask is Intel-only and
                                         # deprecated; this one is Apple
                                         # Silicon-native and actively built
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m backend.scripts.generate_calibration_card   # writes assets/calibration-marker.png
                                                        # (already checked in — only needed if you change it)
```

Print `assets/calibration-marker.png` at exactly 40×40mm — actual size /
100% scale, not "fit to page". Verify with a ruler once; printer scaling
error is the single biggest source of measurement error in this pipeline.

## Run

```bash
source .venv/bin/activate
uvicorn backend.app:app --reload
```

Open http://localhost:8000.

## Shooting the photos

- Plain, high-contrast background (a sheet of paper works well).
- Include the printed calibration marker flat in frame, fully visible, for
  both shots — used to convert pixels to millimeters.
- Top-down photo: straight overhead.
- Side photo: straight-on from the side, item resting on the same surface
  as the marker.

Auto-detection is a starting point, not gospel — the review step lets you
drag-correct the outline and adjust the height before generating.

## What v1 does and doesn't do

See the project plan for the full MVP spec. In short: one item → one bin,
rectangular-or-custom silhouette pocket via a straight top-down extrusion
(won't hug a shape that bulges or narrows at different heights), STL output
only — no slicing or print dispatch, that's on you in Bambu Studio.

---

Built with [Claude Code](https://claude.com/claude-code).
