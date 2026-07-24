import numpy as np
import pytest
import trimesh

from mesh_screenshot.analysis import boundary_edges
from mesh_screenshot.renderer import RenderOptions, render_views
from mesh_screenshot.views import generate_cameras


def _cube_cameras():
    box = trimesh.creation.box(extents=(1, 1, 1))
    cams = generate_cameras(box.bounds.mean(axis=0), 1.0, view_set=6)
    return box, cams


def test_render_options_defaults():
    opts = RenderOptions()
    assert opts.show_boundary is True
    assert opts.wireframe is False
    assert opts.resolution == (512, 512)


def test_render_returns_arrays(gl_available):
    if not gl_available:
        pytest.skip("no offscreen GL backend available")
    box, cams = _cube_cameras()
    opts = RenderOptions(resolution=(128, 128))
    out = render_views(box, cams, opts, boundary_edges(box))
    assert len(out) == 6
    for label, arr in out:
        assert isinstance(label, str)
        assert arr.shape[0] == 128 and arr.shape[1] == 128
        assert arr.shape[2] == 3
        assert arr.dtype == np.uint8


def test_render_not_blank(gl_available):
    if not gl_available:
        pytest.skip("no offscreen GL backend available")
    box, cams = _cube_cameras()
    out = render_views(box, cams, RenderOptions(resolution=(128, 128)),
                       boundary_edges(box))
    # at least one view has non-uniform pixels (the mesh is visible)
    assert any(arr.std() > 1.0 for _, arr in out)
