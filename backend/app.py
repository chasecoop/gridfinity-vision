"""FastAPI backend: photo upload + CV extraction, manual-edit endpoints,
bin generation, and serving the frontend + generated files.

Run with: uvicorn backend.app:app --reload
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import geometry, storage, vision
from backend.models import BinManifest, Calibration, Point, ReferenceObject, Status

app = FastAPI(title="Gridfinity Vision")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def _get_manifest(bin_id: str) -> BinManifest:
    try:
        return storage.load(bin_id)
    except FileNotFoundError:
        raise HTTPException(404, f"No bin with id {bin_id!r}")


@app.post("/api/photos")
async def upload_photos(
    top_photo: UploadFile = File(...),
    side_photo: UploadFile = File(...),
    reference_size_mm: float = Form(40.0),
    item_name: Optional[str] = Form(None),
):
    manifest = storage.create_draft()
    manifest.item_name = item_name
    manifest.reference_object = ReferenceObject(size_mm=reference_size_mm)

    top_bytes = await top_photo.read()
    side_bytes = await side_photo.read()

    top_path = storage.UPLOADS_DIR / f"{manifest.id}-top.jpg"
    side_path = storage.UPLOADS_DIR / f"{manifest.id}-side.jpg"
    top_path.write_bytes(top_bytes)
    side_path.write_bytes(side_bytes)
    manifest.top_photo_path = str(top_path)
    manifest.side_photo_path = str(side_path)

    try:
        top_img = vision.decode_image(top_bytes)
        px_per_mm_top, polygon = vision.calibrate_and_extract_silhouette(
            top_img, reference_size_mm
        )
        side_img = vision.decode_image(side_bytes)
        px_per_mm_side, height_mm = vision.calibrate_and_extract_height(
            side_img, reference_size_mm
        )
    except vision.DetectionError as e:
        raise HTTPException(422, str(e))

    manifest.calibration = Calibration(
        px_per_mm_top=px_per_mm_top, px_per_mm_side=px_per_mm_side
    )
    manifest.silhouette_polygon = [Point(x=x, y=y) for x, y in polygon]
    manifest.height_mm = height_mm
    manifest.status = Status.draft

    storage.save(manifest)
    return manifest


@app.put("/api/photos/{bin_id}/silhouette")
async def update_silhouette(bin_id: str, points: list[Point]):
    manifest = _get_manifest(bin_id)
    manifest.silhouette_polygon = points
    manifest.status = Status.edited
    storage.save(manifest)
    return manifest


@app.put("/api/photos/{bin_id}/height")
async def update_height(bin_id: str, height_mm: float):
    manifest = _get_manifest(bin_id)
    manifest.height_mm = height_mm
    manifest.status = Status.edited
    storage.save(manifest)
    return manifest


@app.post("/api/bins/{bin_id}/params")
async def compute_params(bin_id: str):
    """Auto-computes grid_x/grid_y/bin_height_units as editable suggestions."""
    manifest = _get_manifest(bin_id)
    params = geometry.compute_bin_params(manifest)
    manifest.grid_x = params["grid_x"]
    manifest.grid_y = params["grid_y"]
    manifest.bin_height_units = params["bin_height_units"]
    storage.save(manifest)
    return manifest


@app.post("/api/bins/{bin_id}/generate")
async def generate_bin(
    bin_id: str,
    grid_x: Optional[int] = None,
    grid_y: Optional[int] = None,
    bin_height_units: Optional[int] = None,
    clearance_mm: Optional[float] = None,
):
    manifest = _get_manifest(bin_id)
    if clearance_mm is not None:
        manifest.clearance_mm = clearance_mm
    if grid_x is not None:
        manifest.grid_x = grid_x
    if grid_y is not None:
        manifest.grid_y = grid_y
    if bin_height_units is not None:
        manifest.bin_height_units = bin_height_units

    if manifest.grid_x is None or manifest.grid_y is None or manifest.bin_height_units is None:
        params = geometry.compute_bin_params(manifest)
        manifest.grid_x = manifest.grid_x or params["grid_x"]
        manifest.grid_y = manifest.grid_y or params["grid_y"]
        manifest.bin_height_units = manifest.bin_height_units or params["bin_height_units"]

    try:
        stl_path = geometry.render_stl(manifest)
    except geometry.GeometryError as e:
        raise HTTPException(500, str(e))

    manifest.output_stl_path = str(stl_path)
    manifest.status = Status.generated
    storage.save(manifest)
    return manifest


@app.get("/api/bins")
async def list_bins():
    return storage.list_all()


@app.get("/api/bins/{bin_id}")
async def get_bin(bin_id: str):
    return _get_manifest(bin_id)


@app.get("/api/bins/{bin_id}/stl")
async def get_stl(bin_id: str):
    manifest = _get_manifest(bin_id)
    if not manifest.output_stl_path or not Path(manifest.output_stl_path).exists():
        raise HTTPException(404, "STL not generated yet.")
    return FileResponse(manifest.output_stl_path, media_type="model/stl",
                         filename=f"{manifest.item_name or manifest.id}.stl")


@app.get("/api/bins/{bin_id}/photo/{which}")
async def get_photo(bin_id: str, which: str):
    manifest = _get_manifest(bin_id)
    path = manifest.top_photo_path if which == "top" else manifest.side_photo_path
    if which not in ("top", "side") or not path or not Path(path).exists():
        raise HTTPException(404, "Photo not found.")
    return FileResponse(path)


app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

# Static frontend last, so it doesn't shadow the /api and /assets routes above.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
