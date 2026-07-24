"""Generate labeled camera views on a cube around the mesh. No GL."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

VIEW_SETS: tuple[int, ...] = (6, 14, 26)

_FACES = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
_CORNERS = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
_EDGES = (
    [(x, y, 0) for x in (-1, 1) for y in (-1, 1)]
    + [(x, 0, z) for x in (-1, 1) for z in (-1, 1)]
    + [(0, y, z) for y in (-1, 1) for z in (-1, 1)]
)


@dataclass
class CameraSpec:
    label: str
    direction: np.ndarray
    position: np.ndarray
    up: np.ndarray
    focal_point: np.ndarray


def _int_directions(view_set: int) -> list[tuple[int, int, int]]:
    if view_set == 6:
        return list(_FACES)
    if view_set == 14:
        return list(_FACES) + list(_CORNERS)
    if view_set == 26:
        return list(_FACES) + list(_EDGES) + list(_CORNERS)
    raise ValueError(f"view_set must be one of {VIEW_SETS}, got {view_set}")


def _sign_label(vec: tuple[int, int, int]) -> str:
    names = ("X", "Y", "Z")
    parts = []
    for value, name in zip(vec, names):
        if value > 0:
            parts.append("+" + name)
        elif value < 0:
            parts.append("-" + name)
    return "".join(parts)


def _up_for(direction: np.ndarray) -> np.ndarray:
    world_up = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(direction, world_up))) > 0.999:
        world_up = np.array([0.0, 1.0, 0.0])
    return world_up


def generate_cameras(
    centroid: np.ndarray,
    radius: float,
    view_set: int = 14,
    fov_deg: float = 30.0,
    margin: float = 1.1,
) -> list[CameraSpec]:
    """Cameras looking at ``centroid`` from cube directions, auto-framed."""
    centroid = np.asarray(centroid, dtype=float)
    safe_radius = max(float(radius), 1e-9)
    distance = margin * safe_radius / math.sin(math.radians(fov_deg / 2.0))

    cameras: list[CameraSpec] = []
    for vec in _int_directions(view_set):
        direction = np.asarray(vec, dtype=float)
        direction /= np.linalg.norm(direction)
        position = centroid + direction * distance
        cameras.append(
            CameraSpec(
                label=_sign_label(vec),
                direction=direction,
                position=position,
                up=_up_for(direction),
                focal_point=centroid.copy(),
            )
        )
    return cameras
