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
    n_boundary_components: int
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


def count_boundary_components(edges: np.ndarray) -> int:
    """Connected components of the boundary-edge graph.

    For a manifold boundary — every boundary vertex shared by exactly two
    boundary edges — this equals the number of holes. It undercounts when two
    otherwise-separate openings meet at a single non-manifold ("bowtie")
    vertex, because such openings form one connected component. That is why
    this reports *components* rather than claiming an exact loop count.
    """
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
    """True only when the mesh carries per-element color data of the right size.

    A bare ``trimesh.PointCloud`` always reports ``visual.kind == "vertex"``
    even with no colors attached, so the kind alone is not sufficient — the
    color array must actually have one entry per vertex or face.
    """
    visual = getattr(mesh, "visual", None)
    if visual is None:
        return False
    try:
        kind = visual.kind
    except Exception:  # noqa: BLE001 - some visuals raise on empty access
        return False

    if kind == "texture":
        return True
    if kind not in ("vertex", "face"):
        return False

    try:
        if kind == "face":
            colors = np.asarray(visual.face_colors)
            expected = len(mesh.faces)
        else:
            colors = np.asarray(visual.vertex_colors)
            expected = len(mesh.vertices)
    except Exception:  # noqa: BLE001 - color access is best-effort
        return False

    return expected > 0 and colors.ndim == 2 and len(colors) == expected


def compute_stats(mesh, edges: np.ndarray, has_color: bool) -> MeshStats:
    """Assemble a MeshStats from a mesh plus precomputed boundary edges."""
    verts = np.asarray(getattr(mesh, "vertices", np.empty((0, 3))), dtype=float)

    # trimesh returns bounds=None for geometry with no vertices.
    raw_bounds = getattr(mesh, "bounds", None)
    bounds = np.asarray(raw_bounds, dtype=float) if raw_bounds is not None else None
    if bounds is not None and bounds.shape == (2, 3):
        centroid = bounds.mean(axis=0)
        dims = bounds[1] - bounds[0]
    else:
        centroid = np.zeros(3, dtype=float)
        dims = np.zeros(3, dtype=float)

    radius = (
        float(np.linalg.norm(verts - centroid, axis=1).max()) if len(verts) else 0.0
    )
    faces = getattr(mesh, "faces", None)
    n_faces = len(faces) if faces is not None else 0
    watertight = bool(getattr(mesh, "is_watertight", False)) if n_faces else False
    return MeshStats(
        n_vertices=int(len(verts)),
        n_faces=int(n_faces),
        is_watertight=watertight,
        n_boundary_edges=int(len(edges)),
        n_boundary_components=count_boundary_components(edges),
        bbox_dims=(float(dims[0]), float(dims[1]), float(dims[2])),
        centroid=centroid,
        radius=radius,
        has_color=has_color,
    )
