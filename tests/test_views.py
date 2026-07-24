import math

import numpy as np

from mesh_screenshot.views import CameraSpec, VIEW_SETS, generate_cameras


def test_view_set_counts():
    c = np.zeros(3)
    assert len(generate_cameras(c, 1.0, view_set=6)) == 6
    assert len(generate_cameras(c, 1.0, view_set=14)) == 14
    assert len(generate_cameras(c, 1.0, view_set=26)) == 26


def test_labels_present_and_unique():
    cams = generate_cameras(np.zeros(3), 1.0, view_set=14)
    labels = [c.label for c in cams]
    assert len(set(labels)) == 14
    assert "+X" in labels
    assert "+X+Y+Z" in labels


def test_directions_are_unit_and_typed():
    cams = generate_cameras(np.zeros(3), 1.0, view_set=14)
    for cam in cams:
        assert isinstance(cam, CameraSpec)
        np.testing.assert_allclose(np.linalg.norm(cam.direction), 1.0, atol=1e-9)


def test_autoframe_distance():
    radius, fov, margin = 3.0, 30.0, 1.1
    cams = generate_cameras(np.zeros(3), radius, view_set=6,
                            fov_deg=fov, margin=margin)
    expected = margin * radius / math.sin(math.radians(fov / 2))
    cam = next(c for c in cams if c.label == "+X")
    np.testing.assert_allclose(np.linalg.norm(cam.position), expected, rtol=1e-6)


def test_up_avoids_parallel_to_z():
    cams = generate_cameras(np.zeros(3), 1.0, view_set=6)
    top = next(c for c in cams if c.label == "+Z")
    # +Z view must not use a world-up parallel to its direction
    assert abs(np.dot(top.up, top.direction)) < 0.9


def test_view_sets_constant():
    assert VIEW_SETS == (6, 14, 26)
