"""The only GL module: render a mesh from each camera with PyVista offscreen."""

from __future__ import annotations

from dataclasses import dataclass, field

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


def _to_polydata(mesh):
    import pyvista as pv

    faces = np.asarray(mesh.faces)
    padded = np.hstack(
        [np.full((len(faces), 1), 3, dtype=np.int64), faces.astype(np.int64)]
    ).ravel()
    return pv.PolyData(np.asarray(mesh.vertices, dtype=float), padded)


def _extract_rgb(mesh):
    """Return ('face'|'vertex', Nx3 uint8) or (None, None)."""
    visual = getattr(mesh, "visual", None)
    kind = getattr(visual, "kind", None)
    try:
        if kind == "face":
            return "face", np.asarray(visual.face_colors)[:, :3]
        if kind == "vertex":
            return "vertex", np.asarray(visual.vertex_colors)[:, :3]
        if kind == "texture":
            vc = visual.to_color().vertex_colors
            return "vertex", np.asarray(vc)[:, :3]
    except Exception:  # noqa: BLE001 - color extraction is best-effort
        return None, None
    return None, None


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

    try:
        plotter = pv.Plotter(off_screen=True, window_size=[w, h])
        plotter.background_color = options.background

        if has_faces:
            poly = _to_polydata(mesh)
            ckind, colors = _extract_rgb(mesh) if options.use_color else (None, None)
            if colors is not None:
                if ckind == "face":
                    poly.cell_data["RGB"] = colors.astype(np.uint8)
                else:
                    poly.point_data["RGB"] = colors.astype(np.uint8)
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
            cloud = pv.PolyData(np.asarray(mesh.vertices, dtype=float))
            plotter.add_mesh(cloud, color="lightgray", point_size=3,
                             render_points_as_spheres=True)

        results: list[tuple[str, np.ndarray]] = []
        for cam in cameras:
            plotter.camera_position = [
                tuple(cam.position), tuple(cam.focal_point), tuple(cam.up),
            ]
            plotter.reset_camera()
            img = plotter.screenshot(return_img=True)
            results.append((cam.label, np.asarray(img, dtype=np.uint8)[:, :, :3]))
        plotter.close()
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
