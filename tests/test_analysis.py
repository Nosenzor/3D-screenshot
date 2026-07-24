import numpy as np
import trimesh

from mesh_screenshot.analysis import (
    MeshStats,
    boundary_edges,
    compute_stats,
    count_boundary_components,
    mesh_has_color,
)


def _triangle():
    v = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float)
    f = np.array([[0, 1, 2]])
    return trimesh.Trimesh(vertices=v, faces=f, process=False)


def _square():
    v = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float)
    f = np.array([[0, 1, 2], [0, 2, 3]])
    return trimesh.Trimesh(vertices=v, faces=f, process=False)


def test_closed_cube_has_no_boundary():
    box = trimesh.creation.box(extents=(1, 1, 1))
    assert len(boundary_edges(box)) == 0
    assert box.is_watertight is True


def test_triangle_boundary_edges_and_loop():
    tri = _triangle()
    be = boundary_edges(tri)
    assert len(be) == 3
    assert count_boundary_components(be) == 1


def test_square_shares_diagonal():
    sq = _square()
    be = boundary_edges(sq)
    assert len(be) == 4  # 4 perimeter edges; shared diagonal excluded
    assert count_boundary_components(be) == 1


def test_has_color_detection():
    box = trimesh.creation.box(extents=(1, 1, 1))
    assert mesh_has_color(box) is False
    box.visual.face_colors = np.tile([200, 10, 10, 255], (len(box.faces), 1))
    assert mesh_has_color(box) is True


def test_compute_stats_fields():
    box = trimesh.creation.box(extents=(2, 4, 6))
    be = boundary_edges(box)
    stats = compute_stats(box, be, has_color=False)
    assert isinstance(stats, MeshStats)
    assert stats.n_faces == len(box.faces)
    assert stats.is_watertight is True
    assert stats.n_boundary_edges == 0
    assert stats.n_boundary_components == 0
    np.testing.assert_allclose(sorted(stats.bbox_dims), [2, 4, 6])
    assert stats.radius > 0
