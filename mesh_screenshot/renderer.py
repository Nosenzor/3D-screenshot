"""The only GL module: render a mesh from each camera with PyVista offscreen."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .errors import RenderBackendError
from .views import CameraSpec


@dataclass
class RenderOptions:
    resolution: tuple[int, int] = (512, 512)
    show_boundary: bool = True
    boundary_color: str = "red"
    boundary_width: float = 4.0
    wireframe: bool = False
    background: str = "white"
    use_color: bool = True
    # Must match the fov_deg used by views.generate_cameras(), otherwise the
    # auto-framed camera distance produces the wrong framing.
    fov_deg: float = 30.0


def _to_polydata(mesh):
    import pyvista as pv

    faces = np.asarray(mesh.faces)
    padded = np.hstack(
        [np.full((len(faces), 1), 3, dtype=np.int64), faces.astype(np.int64)]
    ).ravel()
    return pv.PolyData(np.asarray(mesh.vertices, dtype=float), padded)


def _extract_rgb(mesh):
    """Return ('face'|'vertex', Nx3 uint8) or (None, None).

    Returns (None, None) unless the color array is 2-D and non-empty; a bare
    PointCloud reports kind 'vertex' while carrying a zero-length color array.
    """
    visual = getattr(mesh, "visual", None)
    kind = getattr(visual, "kind", None)
    try:
        if kind == "face":
            colors = np.asarray(visual.face_colors)
        elif kind == "vertex":
            colors = np.asarray(visual.vertex_colors)
        elif kind == "texture":
            colors = np.asarray(visual.to_color().vertex_colors)
            kind = "vertex"
        else:
            return None, None
    except Exception:  # noqa: BLE001 - color extraction is best-effort
        return None, None

    if colors.ndim != 2 or len(colors) == 0 or colors.shape[1] < 3:
        return None, None
    return kind, colors[:, :3]


def _edges_polydata(vertices, edges):
    import pyvista as pv

    edges = np.asarray(edges, dtype=np.int64)
    lines = np.hstack(
        [np.full((len(edges), 1), 2, dtype=np.int64), edges]
    ).ravel()
    return pv.PolyData(np.asarray(vertices, dtype=float), lines=lines)


def render_views(
    mesh,
    cameras: list[CameraSpec],
    options: RenderOptions,
    boundary_edges: np.ndarray | None = None,
) -> list[tuple[str, np.ndarray]]:
    """Render each camera; return (label, HxWx3 uint8) list."""
    try:
        import pyvista as pv
    except Exception as exc:  # noqa: BLE001
        raise RenderBackendError(
            "PyVista is not installed. Install with: pip install pyvista"
        ) from exc

    has_faces = getattr(mesh, "faces", None) is not None and len(mesh.faces) > 0
    w, h = options.resolution

    plotter = None
    try:
        plotter = pv.Plotter(off_screen=True, window_size=[w, h])
        plotter.background_color = options.background

        ckind, colors = _extract_rgb(mesh) if options.use_color else (None, None)

        if has_faces:
            poly = _to_polydata(mesh)
            if colors is not None and ckind == "face" and len(colors) == poly.n_cells:
                poly.cell_data["RGB"] = colors.astype(np.uint8)
            elif colors is not None and ckind == "vertex" \
                    and len(colors) == poly.n_points:
                poly.point_data["RGB"] = colors.astype(np.uint8)
            else:
                colors = None

            if colors is not None:
                plotter.add_mesh(poly, scalars="RGB", rgb=True,
                                 show_edges=options.wireframe)
            else:
                plotter.add_mesh(poly, color="lightgray",
                                 show_edges=options.wireframe)

            if options.show_boundary and boundary_edges is not None \
                    and len(boundary_edges) > 0:
                edge_poly = _edges_polydata(mesh.vertices, boundary_edges)
                plotter.add_mesh(edge_poly, color=options.boundary_color,
                                 line_width=options.boundary_width)
        else:
            # NOTE: render_points_as_spheres=True draws nothing in some
            # offscreen GL contexts (point sprites unsupported), which silently
            # produced blank tiles for every point cloud. Plain points are
            # portable, so keep them.
            cloud = pv.PolyData(np.asarray(mesh.vertices, dtype=float))
            if colors is not None and len(colors) == cloud.n_points:
                cloud.point_data["RGB"] = colors.astype(np.uint8)
                plotter.add_mesh(cloud, scalars="RGB", rgb=True, point_size=4)
            else:
                plotter.add_mesh(cloud, color="dimgray", point_size=4)

        # Honor the camera distance computed in views.py: match the plotter's
        # vertical FOV to the fov used for auto-framing and do NOT reset_camera(),
        # which would discard that distance in favor of VTK's own AABB fit.
        plotter.camera.view_angle = options.fov_deg

        results: list[tuple[str, np.ndarray]] = []
        for cam in cameras:
            plotter.camera_position = [
                tuple(cam.position), tuple(cam.focal_point), tuple(cam.up),
            ]
            # Recompute near/far for this distance; we never call reset_camera()
            # because that would override the auto-framed camera distance.
            plotter.renderer.reset_camera_clipping_range()
            # Moving the camera alone does not invalidate the offscreen frame:
            # without an explicit render() every screenshot returns the FIRST
            # view, so all tiles come out identical.
            plotter.render()
            img = plotter.screenshot(return_img=True)
            results.append((cam.label, np.asarray(img, dtype=np.uint8)[:, :, :3]))
        return results
    except RenderBackendError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RenderBackendError(
            "Offscreen rendering failed. On headless Linux, install OSMesa "
            "or run under a virtual display, e.g. `xvfb-run python -m "
            "mesh_screenshot ...`. "
            f"Underlying error: {exc}"
        ) from exc
    finally:
        if plotter is not None:
            plotter.close()
