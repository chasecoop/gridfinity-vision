"""Computer vision: turns a top-down photo + a side photo (each containing
the printed calibration marker) into a silhouette polygon and a height.

Deliberately NOT photogrammetry / 3D reconstruction — see the project plan.
A Gridfinity pocket is a straight extrusion of a 2D outline, so all we need
is: (1) real-world scale from the marker, (2) the item's outline from
directly above, (3) the item's height from the side. Each is a solved
classical-CV problem; no depth estimation or multi-view reconstruction.

Auto-detection here is a best-effort starting point — the frontend lets the
user drag-correct the polygon and height line before generating, which is
the safety net for whatever this gets wrong.
"""
from __future__ import annotations

import cv2
import numpy as np

MARKER_DICT = cv2.aruco.DICT_4X4_50
MARKER_ID = 0  # must match backend/scripts/generate_calibration_card.py

# Simplify detected contours to at most this many polygon vertices — keeps
# the OpenSCAD render fast and the geometry printable (a noisy 300-point
# contour makes for a slow, jagged pocket wall).
MAX_POLYGON_POINTS = 40


class DetectionError(Exception):
    """Raised when the calibration marker can't be found in a photo."""


def _detect_marker(image_bgr: np.ndarray) -> np.ndarray:
    """Returns the marker's 4 corners in pixel coords, shape (4, 2)."""
    dictionary = cv2.aruco.getPredefinedDictionary(MARKER_DICT)
    detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(image_bgr)
    if ids is None or len(ids) == 0:
        raise DetectionError(
            "Couldn't find the calibration marker in this photo. Make sure "
            "it's fully visible, well-lit, and not blurry."
        )
    idx = list(ids.flatten()).index(MARKER_ID) if MARKER_ID in ids.flatten() else 0
    return corners[idx].reshape(4, 2)


def _px_per_mm(marker_corners: np.ndarray, marker_size_mm: float) -> float:
    side_lengths = [
        np.linalg.norm(marker_corners[i] - marker_corners[(i + 1) % 4])
        for i in range(4)
    ]
    avg_side_px = float(np.mean(side_lengths))
    return avg_side_px / marker_size_mm


def _item_mask(image_bgr: np.ndarray, marker_corners: np.ndarray) -> np.ndarray:
    """Thresholds the item against its background and blanks out the
    marker region so it's never mistaken for the item. Assumes a plain,
    reasonably high-contrast background (e.g. a sheet of paper / mat) —
    documented as a shooting condition, not handled generically.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Otsu picks whichever side is "foreground" — if it picked the (larger)
    # background instead of the item, invert.
    if np.count_nonzero(mask) > mask.size * 0.5:
        mask = cv2.bitwise_not(mask)

    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    # Blank out the marker (with margin) so it's excluded from contour search.
    marker_poly = marker_corners.astype(np.int32)
    marker_poly = _expand_poly(marker_poly, factor=1.6)
    cv2.fillPoly(mask, [marker_poly], 0)

    return mask


def _expand_poly(poly: np.ndarray, factor: float) -> np.ndarray:
    center = poly.mean(axis=0)
    return ((poly - center) * factor + center).astype(np.int32)


def _largest_contour(mask: np.ndarray) -> np.ndarray:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise DetectionError(
            "Couldn't find the item's outline. Try a plainer background "
            "and more even lighting."
        )
    return max(contours, key=cv2.contourArea)


def _simplify_contour(contour: np.ndarray, max_points: int) -> np.ndarray:
    perimeter = cv2.arcLength(contour, True)
    epsilon = 0.001 * perimeter
    approx = contour
    for _ in range(20):
        approx = cv2.approxPolyDP(contour, epsilon, True)
        if len(approx) <= max_points:
            break
        epsilon *= 1.5
    return approx.reshape(-1, 2)


def calibrate_and_extract_silhouette(
    image_bgr: np.ndarray, marker_size_mm: float
) -> tuple[float, list[tuple[float, float]]]:
    """Returns (px_per_mm, polygon points in mm, item-local origin)."""
    marker_corners = _detect_marker(image_bgr)
    px_per_mm = _px_per_mm(marker_corners, marker_size_mm)

    mask = _item_mask(image_bgr, marker_corners)
    contour = _largest_contour(mask)
    points_px = _simplify_contour(contour, MAX_POLYGON_POINTS)

    points_mm = points_px / px_per_mm
    # Anchor to the polygon's own bounding-box min corner — geometry.py
    # re-centers this within the bin footprint, so only the shape matters.
    min_xy = points_mm.min(axis=0)
    points_mm = points_mm - min_xy

    return px_per_mm, [(float(x), float(y)) for x, y in points_mm]


def calibrate_and_extract_height(
    image_bgr: np.ndarray, marker_size_mm: float
) -> tuple[float, float]:
    """Returns (px_per_mm, height_mm) from a side-on photo."""
    marker_corners = _detect_marker(image_bgr)
    px_per_mm = _px_per_mm(marker_corners, marker_size_mm)

    mask = _item_mask(image_bgr, marker_corners)
    contour = _largest_contour(mask)
    _, _, _, h_px = cv2.boundingRect(contour)
    height_mm = h_px / px_per_mm

    return px_per_mm, float(height_mm)


def decode_image(raw_bytes: bytes) -> np.ndarray:
    array = np.frombuffer(raw_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise DetectionError("Couldn't read that file as an image.")
    return image
