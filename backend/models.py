"""Pydantic schemas for the bin manifest — the one record per generated bin.

There is no database. Each manifest is persisted as bins/<id>.json by
storage.py. This module is just the shape of that record.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Status(str, Enum):
    draft = "draft"       # photos uploaded, auto-detection ran
    edited = "edited"     # user adjusted silhouette and/or height
    generated = "generated"  # STL has been rendered


class ReferenceObject(BaseModel):
    type: str = "aruco_calibration_card"
    size_mm: float


class Calibration(BaseModel):
    px_per_mm_top: Optional[float] = None
    px_per_mm_side: Optional[float] = None


class Point(BaseModel):
    x: float
    y: float


class BinManifest(BaseModel):
    id: str
    created_at: str
    item_name: Optional[str] = None

    top_photo_path: Optional[str] = None
    side_photo_path: Optional[str] = None

    reference_object: Optional[ReferenceObject] = None
    calibration: Calibration = Field(default_factory=Calibration)

    # Silhouette polygon in mm, in the item's own local space (not yet
    # positioned within a bin). Origin/scale are whatever vision.py produced;
    # geometry.py is responsible for centering it inside the bin footprint.
    silhouette_polygon: list[Point] = Field(default_factory=list)
    height_mm: Optional[float] = None

    # Bin parameters — auto-computed by geometry.py, editable before generate.
    grid_x: Optional[int] = None
    grid_y: Optional[int] = None
    bin_height_units: Optional[int] = None
    clearance_mm: float = 2.0

    status: Status = Status.draft
    output_stl_path: Optional[str] = None
