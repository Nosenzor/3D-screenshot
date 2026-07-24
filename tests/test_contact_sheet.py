import numpy as np

from mesh_screenshot.analysis import MeshStats
from mesh_screenshot.contact_sheet import compose_contact_sheet, grid_dims


def _stats():
    return MeshStats(
        n_vertices=8, n_faces=12, is_watertight=True,
        n_boundary_edges=0, n_boundary_loops=0,
        bbox_dims=(1.0, 2.0, 3.0), centroid=np.zeros(3),
        radius=1.87, has_color=False,
    )


def _tiles(n, size=(64, 64)):
    out = []
    for i in range(n):
        arr = np.full((size[1], size[0], 3), i * 3 % 256, dtype=np.uint8)
        out.append((f"V{i}", arr))
    return out


def test_grid_dims():
    assert grid_dims(7) == (3, 3)    # 6 views + stats
    assert grid_dims(15) == (4, 4)   # 14 views + stats
    assert grid_dims(27) == (5, 6)   # 26 views + stats


def test_compose_size_for_14_views():
    img = compose_contact_sheet(_tiles(14), _stats(), "model.ply",
                                tile_size=(100, 100))
    # 15 cells -> 4x4 grid -> 400x400
    assert img.size == (400, 400)


def test_compose_size_for_6_views():
    img = compose_contact_sheet(_tiles(6), _stats(), "model.ply",
                                tile_size=(100, 100))
    # 7 cells -> 3x3 grid -> 300x300
    assert img.size == (300, 300)


def test_returns_rgb_image():
    img = compose_contact_sheet(_tiles(14), _stats(), "x.ply",
                                tile_size=(50, 50))
    assert img.mode == "RGB"
