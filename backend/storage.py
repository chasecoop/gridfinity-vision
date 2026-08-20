"""File-based persistence: one JSON manifest per bin under bins/, photos
under uploads/, rendered STLs under output/. No database — this is a
single-user local tool.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.models import BinManifest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOADS_DIR = PROJECT_ROOT / "uploads"
OUTPUT_DIR = PROJECT_ROOT / "output"
BINS_DIR = PROJECT_ROOT / "bins"

for _dir in (UPLOADS_DIR, OUTPUT_DIR, BINS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def manifest_path(bin_id: str) -> Path:
    return BINS_DIR / f"{bin_id}.json"


def save(manifest: BinManifest) -> None:
    manifest_path(manifest.id).write_text(manifest.model_dump_json(indent=2))


def load(bin_id: str) -> BinManifest:
    path = manifest_path(bin_id)
    if not path.exists():
        raise FileNotFoundError(f"No bin manifest with id {bin_id!r}")
    return BinManifest.model_validate_json(path.read_text())


def list_all() -> list[BinManifest]:
    manifests = [
        BinManifest.model_validate_json(p.read_text())
        for p in sorted(BINS_DIR.glob("*.json"))
    ]
    manifests.sort(key=lambda m: m.created_at, reverse=True)
    return manifests


def create_draft() -> BinManifest:
    return BinManifest(
        id=new_id(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
