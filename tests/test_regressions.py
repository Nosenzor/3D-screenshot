"""Regression tests for defects found in code review of the initial build.

Each test names the finding it locks down so the intent survives refactoring.
"""

import argparse

import numpy as np
import pytest
import trimesh

from mesh_screenshot import analysis
from mesh_screenshot.cli import main, parse_resolution
from mesh_screenshot.contact_sheet import compose_contact_sheet
from mesh_screenshot.renderer import RenderOptions, render_views
from mesh_screenshot.views import generate_cameras


def _box(extents=(1, 1, 1)):
    return trimesh.creation.box(extents=extents)


def _stats_for(mesh):
    edges = analysis.boundary_edges(mesh)
    return analysis.compute_stats(mesh, edges, analysis.mesh_has_color(mesh))


# --- Finding 1: colliding input stems silently overwrote each other ---------

def test_colliding_stems_do_not_overwrite(tmp_path):
    a_dir, b_dir = tmp_path / "a", tmp_path / "b"
    a_dir.mkdir()
    b_dir.mkdir()
    _box((1, 1, 1)).export(a_dir / "model.ply")
    _box((4, 4, 4)).export(b_dir / "model.ply")
    out = tmp_path / "out"

    code = main([str(a_dir / "model.ply"), str(b_dir / "model.ply"),
                 "-o", str(out), "--views", "6", "--resolution", "64x64"])

    assert code == 0
    sheets = sorted(p.name for p in out.glob("*_contact.png"))
    assert sheets == ["model_2_contact.png", "model_contact.png"], sheets


def test_colliding_stems_individual_dirs_are_distinct(tmp_path):
    a_dir, b_dir = tmp_path / "a", tmp_path / "b"
    a_dir.mkdir()
    b_dir.mkdir()
    _box().export(a_dir / "m.ply")
    _box().export(b_dir / "m.ply")
    out = tmp_path / "out"

    code = main([str(a_dir / "m.ply"), str(b_dir / "m.ply"), "-o", str(out),
                 "--views", "6", "--resolution", "64x64", "--individual"])

    assert code == 0
    assert (out / "m_views").is_dir()
    assert (out / "m_2_views").is_dir()


# --- Finding 2: Plotter leaked when screenshot() raised mid-loop ------------

def test_plotter_closed_when_render_fails(monkeypatch, gl_available):
    if not gl_available:
        pytest.skip("no offscreen GL backend available")
    import pyvista as pv

    from mesh_screenshot.errors import RenderBackendError

    box = _box()
    cams = generate_cameras(box.bounds.mean(axis=0), 1.0, view_set=6)

    created: list[pv.Plotter] = []
    real_init = pv.Plotter.__init__

    def tracking_init(self, *a, **kw):
        real_init(self, *a, **kw)
        created.append(self)

    def boom(self, *a, **kw):
        raise RuntimeError("simulated GL failure")

    monkeypatch.setattr(pv.Plotter, "__init__", tracking_init)
    monkeypatch.setattr(pv.Plotter, "screenshot", boom)

    with pytest.raises(RenderBackendError):
        render_views(box, cams, RenderOptions(resolution=(64, 64)),
                     analysis.boundary_edges(box))

    assert created, "expected a Plotter to have been constructed"
    assert all(p._closed for p in created), "plotter leaked on the error path"


# --- Finding 3: boundary components vs loops, honestly named ---------------

def test_bowtie_boundary_reports_components_not_loops():
    # Two triangles sharing only vertex 0: two visually separate openings that
    # touch at one non-manifold vertex, so they form ONE connected component.
    v = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [-1, 0, 0], [0, -1, 0]], float)
    f = np.array([[0, 1, 2], [0, 3, 4]])
    bow = trimesh.Trimesh(vertices=v, faces=f, process=False)
    edges = analysis.boundary_edges(bow)
    assert analysis.count_boundary_components(edges) == 1


def test_disjoint_patches_count_separately():
    a = trimesh.creation.box(extents=(1, 1, 1))
    b = trimesh.creation.box(extents=(1, 1, 1))
    b.apply_translation((10, 0, 0))
    # Drop one face from each box -> two genuinely disjoint boundary loops.
    merged = trimesh.util.concatenate((a, b))
    kept = np.delete(merged.faces, [0, len(a.faces)], axis=0)
    holed = trimesh.Trimesh(vertices=merged.vertices, faces=kept, process=False)
    edges = analysis.boundary_edges(holed)
    assert analysis.count_boundary_components(edges) == 2


# --- Finding 4: auto-framed distance must survive to the actual camera -----

def test_views_are_actually_distinct(gl_available):
    """A stale offscreen frame made every tile identical to the first view."""
    if not gl_available:
        pytest.skip("no offscreen GL backend available")
    # A shape with no rotational symmetry, so every axis view must differ.
    mesh = trimesh.creation.box(extents=(1, 3, 9))
    stats = _stats_for(mesh)
    cams = generate_cameras(stats.centroid, stats.radius, view_set=6)

    out = render_views(mesh, cams, RenderOptions(resolution=(96, 96)),
                       analysis.boundary_edges(mesh))
    assert len(out) == 6
    first = out[0][1]
    differing = [lbl for lbl, img in out[1:] if not np.array_equal(first, img)]
    # +X/-X of a box look alike, but at least the Y and Z views must differ.
    assert len(differing) >= 3, (
        f"only {len(differing)}/5 views differed from '{out[0][0]}' — the "
        "renderer is returning a stale frame instead of re-rendering"
    )


def test_framing_distance_is_honored(gl_available):
    if not gl_available:
        pytest.skip("no offscreen GL backend available")
    import pyvista as pv

    box = _box()
    centroid = box.bounds.mean(axis=0)
    near = generate_cameras(centroid, 1.0, view_set=6, margin=1.1)
    far = generate_cameras(centroid, 1.0, view_set=6, margin=5.0)

    def rendered_silhouette_area(cams):
        out = render_views(box, cams, RenderOptions(resolution=(128, 128)),
                           analysis.boundary_edges(box))
        _, img = next((lbl, im) for lbl, im in out if lbl == "+X")
        # background is white; count non-white pixels as the mesh silhouette
        return int((img.min(axis=2) < 250).sum())

    assert rendered_silhouette_area(near) > rendered_silhouette_area(far), (
        "a larger margin must render the mesh smaller; if these are equal the "
        "computed camera distance is being discarded"
    )
    del pv


# --- Finding 5: bare point cloud must not claim it has color ---------------

def test_bare_point_cloud_has_no_color():
    cloud = trimesh.PointCloud(np.random.RandomState(0).rand(20, 3))
    assert analysis.mesh_has_color(cloud) is False


def test_colored_point_cloud_has_color():
    pts = np.random.RandomState(0).rand(20, 3)
    colors = np.zeros((20, 4), np.uint8)
    colors[:, 0] = 255
    colors[:, 3] = 255
    cloud = trimesh.PointCloud(pts, colors=colors)
    assert analysis.mesh_has_color(cloud) is True


# --- Finding 6: point-cloud colors are actually rendered ------------------

def test_colored_point_cloud_renders_in_color(gl_available):
    if not gl_available:
        pytest.skip("no offscreen GL backend available")
    pts = np.random.RandomState(0).rand(400, 3) * 10.0
    colors = np.zeros((400, 4), np.uint8)
    colors[:, 0] = 255  # pure red
    colors[:, 3] = 255
    cloud = trimesh.PointCloud(pts, colors=colors)
    stats = _stats_for(cloud)
    cams = generate_cameras(stats.centroid, stats.radius, view_set=6)

    out = render_views(cloud, cams, RenderOptions(resolution=(128, 128)), None)
    _, img = out[0]
    reddish = (img[:, :, 0] > 150) & (img[:, :, 1] < 120) & (img[:, :, 2] < 120)
    assert reddish.sum() > 0, "point-cloud vertex colors were not rendered"


def test_uncolored_point_cloud_is_not_blank(gl_available):
    """render_points_as_spheres=True silently produced fully blank tiles."""
    if not gl_available:
        pytest.skip("no offscreen GL backend available")
    pts = np.random.RandomState(1).rand(400, 3) * 10.0
    cloud = trimesh.PointCloud(pts)
    stats = _stats_for(cloud)
    cams = generate_cameras(stats.centroid, stats.radius, view_set=6)

    out = render_views(cloud, cams, RenderOptions(resolution=(128, 128)), None)
    for label, img in out:
        assert (img.min(axis=2) < 250).sum() > 0, f"view {label} rendered blank"


# --- Finding 7: degenerate geometry must not raise a raw numpy error -------

def test_compute_stats_on_empty_mesh():
    empty = trimesh.Trimesh(vertices=np.zeros((0, 3)),
                            faces=np.zeros((0, 3), int), process=False)
    stats = analysis.compute_stats(empty, analysis.boundary_edges(empty), False)
    assert stats.n_vertices == 0
    assert stats.n_faces == 0
    assert stats.radius == 0.0
    assert stats.is_watertight is False
    assert stats.bbox_dims == (0.0, 0.0, 0.0)


def test_compute_stats_on_coincident_vertices():
    v = np.zeros((3, 3), float)
    mesh = trimesh.Trimesh(vertices=v, faces=np.array([[0, 1, 2]]), process=False)
    stats = analysis.compute_stats(mesh, analysis.boundary_edges(mesh), False)
    assert stats.radius == 0.0


# --- Finding 8: absurd --resolution is rejected cleanly, not a traceback ---

def test_resolution_below_minimum_rejected():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_resolution("100x16")


def test_resolution_zero_rejected():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_resolution("0x0")


def test_contact_sheet_survives_short_tiles():
    stats = _stats_for(_box())
    tiles = [("V0", np.zeros((8, 40, 3), np.uint8))]
    # 1 tile + 1 stats panel = 2 cells -> (rows=1, cols=2) -> 80x8
    img = compose_contact_sheet(tiles, stats, "x.ply", tile_size=(40, 8))
    assert img.size == (80, 8)


# --- 26-view set end to end (previously only 6 and 14 were exercised) ------

def test_e2e_26_views(tmp_path, gl_available):
    if not gl_available:
        pytest.skip("no offscreen GL backend available")
    mesh_path = tmp_path / "box.ply"
    _box().export(mesh_path)
    out = tmp_path / "shots"

    code = main([str(mesh_path), "-o", str(out), "--views", "26",
                 "--resolution", "32x32"])

    assert code == 0
    from PIL import Image

    with Image.open(out / "box_contact.png") as img:
        # 26 views + 1 panel = 27 cells -> (rows=5, cols=6) -> 192x160
        assert img.size == (192, 160)
