"""Geometry facts about a mesh: boundary edges, watertightness, stats. No GL."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class MeshStats:
    n_vertices: int
    n_faces: int
    is_watertight: bool
    n_boundary_edges: int
    n_boundary_loops: int
    bbox_dims: tuple[float, float, float]
    centroid: np.ndarray
    radius: float
    has_color: bool


def boundary_edges(mesh) -> np.ndarray:
    """Edges referenced by exactly one face (open borders / holes)."""
    faces = getattr(mesh, "faces", None)
    if faces is None or len(faces) == 0:
        return np.empty((0, 2), dtype=np.int64)
    edges = np.sort(mesh.edges_sorted, axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    return unique[counts == 1].astype(np.int64)


def count_boundary_loops(edges: np.ndarray) -> int:
    """Number of connected components in the boundary-edge graph."""
    if len(edges) == 0:
        return 0
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b in edges:
        union(int(a), int(b))
    return len({find(int(v)) for v in np.unique(edges)})


def mesh_has_color(mesh) -> bool:
    """True when the mesh carries vertex, face, or texture color."""
    visual = getattr(mesh, "visual", None)
    if visual is None:
        return False
    try:
        kind = visual.kind
    except Exception:  # noqa: BLE001 - some visuals raise on empty access
        kind = None
    return kind in ("vertex", "face", "texture")


def compute_stats(mesh, edges: np.ndarray, has_color: bool) -> MeshStats:
    """Assemble a MeshStats from a mesh plus precomputed boundary edges."""
    bounds = np.asarray(mesh.bounds, dtype=float)  # (2, 3)
    centroid = bounds.mean(axis=0)
    dims = bounds[1] - bounds[0]
    verts = np.asarray(mesh.vertices, dtype=float)
    radius = float(np.linalg.norm(verts - centroid, axis=1).max()) if len(verts) else 0.0
    faces = getattr(mesh, "faces", np.empty((0, 3)))
    watertight = bool(getattr(mesh, "is_watertight", False)) if len(faces) else False
    return MeshStats(
        n_vertices=int(len(verts)),
        n_faces=int(len(faces)),
        is_watertight=watertight,
        n_boundary_edges=int(len(edges)),
        n_boundary_loops=count_boundary_loops(edges),
        bbox_dims=(float(dims[0]), float(dims[1]), float(dims[2])),
        centroid=centroid,
        radius=radius,
        has_color=has_color,
    )
