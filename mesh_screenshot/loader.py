"""Load mesh files into a normalized in-memory form using trimesh."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import trimesh

from .errors import MeshLoadError


@dataclass
class LoadedMesh:
    mesh: object  # trimesh.Trimesh or trimesh.PointCloud
    source_path: Path
    is_point_cloud: bool
    scene_flattened: bool


def load_mesh(path: str | Path) -> LoadedMesh:
    """Load ``path`` and normalize scenes to a single concatenated mesh."""
    source = Path(path)
    if not source.exists():
        raise MeshLoadError(f"File not found: {source}")

    try:
        obj = trimesh.load(source, force=None)
    except Exception as exc:  # noqa: BLE001 - surface any loader failure uniformly
        raise MeshLoadError(f"Could not load mesh '{source}': {exc}") from exc

    scene_flattened = False
    if isinstance(obj, trimesh.Scene):
        if len(obj.geometry) == 0:
            raise MeshLoadError(f"Scene contains no geometry: {source}")
        obj = trimesh.util.concatenate(tuple(obj.geometry.values()))
        scene_flattened = True

    if isinstance(obj, trimesh.PointCloud):
        return LoadedMesh(obj, source, is_point_cloud=True,
                          scene_flattened=scene_flattened)

    if isinstance(obj, trimesh.Trimesh):
        return LoadedMesh(obj, source, is_point_cloud=False,
                          scene_flattened=scene_flattened)

    raise MeshLoadError(
        f"Unsupported geometry type '{type(obj).__name__}' in {source}"
    )
