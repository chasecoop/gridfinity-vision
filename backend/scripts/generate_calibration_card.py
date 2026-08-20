"""Generates assets/calibration-marker.png — the printable reference marker
used to calibrate pixels-to-mm in every photo.

Run once (already checked into the repo, re-run only if you want to change
MARKER_ID or MARKER_SIZE_MM — if you do, update the same constants in
backend/vision.py to match):

    python -m backend.scripts.generate_calibration_card
"""
from pathlib import Path

import cv2

MARKER_DICT = cv2.aruco.DICT_4X4_50
MARKER_ID = 0
MARKER_SIZE_MM = 40  # print this marker at exactly 40mm x 40mm, no scaling
IMAGE_PX = 800  # generated at this resolution; print software controls final mm size

OUT_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "calibration-marker.png"


def main() -> None:
    dictionary = cv2.aruco.getPredefinedDictionary(MARKER_DICT)
    marker_img = cv2.aruco.generateImageMarker(dictionary, MARKER_ID, IMAGE_PX)

    # Add a white quiet-zone border — ArUco detection needs margin around
    # the marker to find it reliably.
    border = IMAGE_PX // 8
    bordered = cv2.copyMakeBorder(
        marker_img, border, border, border, border,
        cv2.BORDER_CONSTANT, value=255,
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT_PATH), bordered)
    print(f"Wrote {OUT_PATH} — print at exactly {MARKER_SIZE_MM}x{MARKER_SIZE_MM}mm "
          f"(marker only, border excluded), 100% scale, no 'fit to page'.")


if __name__ == "__main__":
    main()
