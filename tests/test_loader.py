from pathlib import Path

import numpy as np
import trimesh

from mesh_screenshot.errors import MeshLoadError
from mesh_screenshot.loader import LoadedMesh, load_mesh


def test_loads_a_single_mesh(tmp_path):
    box = trimesh.creation.box(extents=(1, 1, 1))
    p = tmp_path / "box.ply"
    box.export(p)

    loaded = load_mesh(p)

    assert isinstance(loaded, LoadedMesh)
    assert loaded.mesh.vertices.shape[1] == 3
    assert len(loaded.mesh.faces) == len(box.faces)
    assert loaded.is_point_cloud is False
    assert loaded.scene_flattened is False
    assert loaded.source_path == Path(p)


def test_flattens_a_scene(tmp_path):
    a = trimesh.creation.box(extents=(1, 1, 1))
    b = trimesh.creation.box(extents=(1, 1, 1))
    b.apply_translation((3, 0, 0))
    scene = trimesh.Scene([a, b])
    p = tmp_path / "two_boxes.glb"
    scene.export(p)

    loaded = load_mesh(p)

    assert loaded.scene_flattened is True
    # concatenation keeps all geometry
    assert len(loaded.mesh.faces) == len(a.faces) + len(b.faces)


def test_loads_a_point_cloud(tmp_path):
    pts = np.random.RandomState(0).rand(50, 3)
    cloud = trimesh.PointCloud(pts)
    p = tmp_path / "cloud.ply"
    cloud.export(p)

    loaded = load_mesh(p)

    assert loaded.is_point_cloud is True
    assert len(loaded.mesh.vertices) == 50


def test_missing_file_raises(tmp_path):
    try:
        load_mesh(tmp_path / "nope.ply")
        assert False, "expected MeshLoadError"
    except MeshLoadError:
        pass
