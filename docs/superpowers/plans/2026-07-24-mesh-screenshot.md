# Mesh Screenshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone tool that renders any mesh to a single labeled multi-view contact-sheet PNG (plus optional per-view PNGs) so an AI agent can run one command, `Read` one image, and reason about 3D geometry.

**Architecture:** A Python package `mesh_screenshot/` with isolated modules: `loader` (trimesh I/O), `analysis` (boundary edges + stats, no GL), `views` (camera generation, no GL), `renderer` (PyVista offscreen, the only GL code), `contact_sheet` (PIL composition, no GL), and `cli` wiring. Everything except `renderer.py` is unit-testable without a GPU. A `.claude/skills/mesh-screenshot/SKILL.md` teaches agents to invoke it.

**Tech Stack:** Python ≥3.10, trimesh (load + geometry), PyVista/VTK (offscreen render), NumPy, Pillow (compose), pytest (tests).

## Global Constraints

- **Python:** `requires-python = ">=3.10"` (uses `X | Y` type syntax).
- **Runtime dependencies (exact list):** `trimesh`, `pyvista`, `numpy`, `pillow`. No others.
- **No domain coupling:** generic mesh tool only. No domain-specific naming, presets, or flags anywhere.
- **Boundary highlight ON by default;** wireframe OFF by default; contact sheet is the default (only) output unless `--individual`.
- **GL isolation:** only `renderer.py` imports/uses `pyvista`. All other modules import cleanly with no display.
- **Friendly failure:** on a failed GL/offscreen context, print a one-line actionable hint (OSMesa / `xvfb-run`), not a raw traceback; exit non-zero.
- **Package invoked as** `python -m mesh_screenshot` and via console script `mesh-screenshot`.
- **Shared errors** live in `mesh_screenshot/errors.py`; every module raises those types.
- **Commit** after each task with the message shown in its final step.

---

## File Structure

```
mesh_screenshot/
  __init__.py          # version
  errors.py            # MeshScreenshotError, MeshLoadError, RenderBackendError
  loader.py            # load_mesh() -> LoadedMesh
  analysis.py          # boundary_edges(), compute_stats() -> MeshStats
  views.py             # generate_cameras() -> list[CameraSpec]
  renderer.py          # render_views() -> list[(label, ndarray)]   (GL)
  contact_sheet.py     # compose_contact_sheet() -> PIL.Image
  cli.py               # main(); argparse + wiring
  __main__.py          # from .cli import main; main()
tests/
  conftest.py          # gl_available fixture
  test_loader.py
  test_analysis.py
  test_views.py
  test_contact_sheet.py
  test_renderer.py     # GL-guarded
  test_cli.py          # e2e
pyproject.toml
.claude/skills/mesh-screenshot/SKILL.md
README.md
```

---

## Task 1: Package scaffolding, packaging, and shared errors

**Files:**
- Create: `mesh_screenshot/__init__.py`
- Create: `mesh_screenshot/errors.py`
- Create: `pyproject.toml`
- Create: `tests/__init__.py` (empty)
- Test: `tests/test_errors.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `mesh_screenshot.__version__: str`
  - `mesh_screenshot.errors.MeshScreenshotError(Exception)`
  - `mesh_screenshot.errors.MeshLoadError(MeshScreenshotError)`
  - `mesh_screenshot.errors.RenderBackendError(MeshScreenshotError)`

- [ ] **Step 1: Write the failing test**

`tests/test_errors.py`:
```python
import mesh_screenshot
from mesh_screenshot.errors import (
    MeshScreenshotError,
    MeshLoadError,
    RenderBackendError,
)


def test_version_is_string():
    assert isinstance(mesh_screenshot.__version__, str)
    assert mesh_screenshot.__version__


def test_error_hierarchy():
    assert issubclass(MeshLoadError, MeshScreenshotError)
    assert issubclass(RenderBackendError, MeshScreenshotError)
    assert issubclass(MeshScreenshotError, Exception)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mesh_screenshot'`.

- [ ] **Step 3: Write minimal implementation**

`mesh_screenshot/__init__.py`:
```python
"""Render any mesh to a labeled multi-view contact-sheet PNG."""

__version__ = "0.1.0"
```

`mesh_screenshot/errors.py`:
```python
"""Exception types shared across the package."""


class MeshScreenshotError(Exception):
    """Base class for all mesh_screenshot errors."""


class MeshLoadError(MeshScreenshotError):
    """Raised when an input file cannot be loaded as a mesh."""


class RenderBackendError(MeshScreenshotError):
    """Raised when the offscreen GL/render backend is unavailable."""
```

`tests/__init__.py`: (empty file)

`pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "mesh-screenshot"
version = "0.1.0"
description = "Render any mesh to a labeled multi-view contact-sheet PNG so AI agents can see 3D geometry."
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "trimesh>=4.0",
    "pyvista>=0.43",
    "numpy>=1.24",
    "pillow>=10.0",
]

[project.optional-dependencies]
test = ["pytest>=7.0"]

[project.scripts]
mesh-screenshot = "mesh_screenshot.cli:main"

[tool.setuptools.packages.find]
include = ["mesh_screenshot*"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_errors.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add mesh_screenshot/__init__.py mesh_screenshot/errors.py pyproject.toml tests/__init__.py tests/test_errors.py
git commit -m "feat: scaffold mesh_screenshot package, packaging, shared errors"
```

---

## Task 2: Mesh loader

**Files:**
- Create: `mesh_screenshot/loader.py`
- Test: `tests/test_loader.py`

**Interfaces:**
- Consumes: `mesh_screenshot.errors.MeshLoadError`.
- Produces:
  - `LoadedMesh` dataclass: fields `mesh` (`trimesh.Trimesh` or `trimesh.PointCloud`), `source_path: pathlib.Path`, `is_point_cloud: bool`, `scene_flattened: bool`.
  - `load_mesh(path: str | pathlib.Path) -> LoadedMesh`.

- [ ] **Step 1: Write the failing test**

`tests/test_loader.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mesh_screenshot.loader'`.

- [ ] **Step 3: Write minimal implementation**

`mesh_screenshot/loader.py`:
```python
"""Load mesh files into a normalized in-memory form using trimesh."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import trimesh

from .errors import MeshLoadError


@dataclass
class LoadedMesh:
    mesh: object  # trimesh.Trimesh or trimesh.PointCloud
    source_path: Path
    is_point_cloud: bool
    scene_flattened: bool


def load_mesh(path: str | Path) -> LoadedMesh:
    """Load ``path`` and normalize scenes to a single concatenated mesh."""
    source = Path(path)
    if not source.exists():
        raise MeshLoadError(f"File not found: {source}")

    try:
        obj = trimesh.load(source, force=None)
    except Exception as exc:  # noqa: BLE001 - surface any loader failure uniformly
        raise MeshLoadError(f"Could not load mesh '{source}': {exc}") from exc

    scene_flattened = False
    if isinstance(obj, trimesh.Scene):
        if len(obj.geometry) == 0:
            raise MeshLoadError(f"Scene contains no geometry: {source}")
        obj = trimesh.util.concatenate(tuple(obj.geometry.values()))
        scene_flattened = True

    if isinstance(obj, trimesh.PointCloud):
        return LoadedMesh(obj, source, is_point_cloud=True,
                          scene_flattened=scene_flattened)

    if isinstance(obj, trimesh.Trimesh):
        return LoadedMesh(obj, source, is_point_cloud=False,
                          scene_flattened=scene_flattened)

    raise MeshLoadError(
        f"Unsupported geometry type '{type(obj).__name__}' in {source}"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_loader.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add mesh_screenshot/loader.py tests/test_loader.py
git commit -m "feat: mesh loader with scene flattening and point-cloud support"
```

---

## Task 3: Geometry analysis (boundary edges + stats)

**Files:**
- Create: `mesh_screenshot/analysis.py`
- Test: `tests/test_analysis.py`

**Interfaces:**
- Consumes: nothing from other tasks (operates on a trimesh mesh directly).
- Produces:
  - `boundary_edges(mesh) -> np.ndarray` — shape `(M, 2)` int array of vertex-index pairs, each edge used by exactly one face; empty `(0, 2)` for point clouds / no faces.
  - `count_boundary_loops(boundary_edges: np.ndarray) -> int`.
  - `mesh_has_color(mesh) -> bool`.
  - `MeshStats` dataclass: `n_vertices: int`, `n_faces: int`, `is_watertight: bool`, `n_boundary_edges: int`, `n_boundary_loops: int`, `bbox_dims: tuple[float, float, float]`, `centroid: np.ndarray (3,)`, `radius: float`, `has_color: bool`.
  - `compute_stats(mesh, boundary_edges: np.ndarray, has_color: bool) -> MeshStats`.

- [ ] **Step 1: Write the failing test**

`tests/test_analysis.py`:
```python
import numpy as np
import trimesh

from mesh_screenshot.analysis import (
    MeshStats,
    boundary_edges,
    compute_stats,
    count_boundary_loops,
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
    assert count_boundary_loops(be) == 1


def test_square_shares_diagonal():
    sq = _square()
    be = boundary_edges(sq)
    assert len(be) == 4  # 4 perimeter edges; shared diagonal excluded
    assert count_boundary_loops(be) == 1


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
    assert stats.n_boundary_loops == 0
    np.testing.assert_allclose(sorted(stats.bbox_dims), [2, 4, 6])
    assert stats.radius > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_analysis.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mesh_screenshot.analysis'`.

- [ ] **Step 3: Write minimal implementation**

`mesh_screenshot/analysis.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_analysis.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add mesh_screenshot/analysis.py tests/test_analysis.py
git commit -m "feat: geometry analysis (boundary edges, loops, watertight, stats)"
```

---

## Task 4: Camera view generation

**Files:**
- Create: `mesh_screenshot/views.py`
- Test: `tests/test_views.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces:
  - `CameraSpec` dataclass: `label: str`, `direction: np.ndarray (3,)` (unit), `position: np.ndarray (3,)`, `up: np.ndarray (3,)`, `focal_point: np.ndarray (3,)`.
  - `VIEW_SETS: tuple[int, ...]` == `(6, 14, 26)`.
  - `generate_cameras(centroid: np.ndarray, radius: float, view_set: int = 14, fov_deg: float = 30.0, margin: float = 1.1) -> list[CameraSpec]`.

- [ ] **Step 1: Write the failing test**

`tests/test_views.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_views.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mesh_screenshot.views'`.

- [ ] **Step 3: Write minimal implementation**

`mesh_screenshot/views.py`:
```python
"""Generate labeled camera views on a cube around the mesh. No GL."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

VIEW_SETS: tuple[int, ...] = (6, 14, 26)

_FACES = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
_CORNERS = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
_EDGES = (
    [(x, y, 0) for x in (-1, 1) for y in (-1, 1)]
    + [(x, 0, z) for x in (-1, 1) for z in (-1, 1)]
    + [(0, y, z) for y in (-1, 1) for z in (-1, 1)]
)


@dataclass
class CameraSpec:
    label: str
    direction: np.ndarray
    position: np.ndarray
    up: np.ndarray
    focal_point: np.ndarray


def _int_directions(view_set: int) -> list[tuple[int, int, int]]:
    if view_set == 6:
        return list(_FACES)
    if view_set == 14:
        return list(_FACES) + list(_CORNERS)
    if view_set == 26:
        return list(_FACES) + list(_EDGES) + list(_CORNERS)
    raise ValueError(f"view_set must be one of {VIEW_SETS}, got {view_set}")


def _sign_label(vec: tuple[int, int, int]) -> str:
    names = ("X", "Y", "Z")
    parts = []
    for value, name in zip(vec, names):
        if value > 0:
            parts.append("+" + name)
        elif value < 0:
            parts.append("-" + name)
    return "".join(parts)


def _up_for(direction: np.ndarray) -> np.ndarray:
    world_up = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(direction, world_up))) > 0.999:
        world_up = np.array([0.0, 1.0, 0.0])
    return world_up


def generate_cameras(
    centroid: np.ndarray,
    radius: float,
    view_set: int = 14,
    fov_deg: float = 30.0,
    margin: float = 1.1,
) -> list[CameraSpec]:
    """Cameras looking at ``centroid`` from cube directions, auto-framed."""
    centroid = np.asarray(centroid, dtype=float)
    safe_radius = max(float(radius), 1e-9)
    distance = margin * safe_radius / math.sin(math.radians(fov_deg / 2.0))

    cameras: list[CameraSpec] = []
    for vec in _int_directions(view_set):
        direction = np.asarray(vec, dtype=float)
        direction /= np.linalg.norm(direction)
        position = centroid + direction * distance
        cameras.append(
            CameraSpec(
                label=_sign_label(vec),
                direction=direction,
                position=position,
                up=_up_for(direction),
                focal_point=centroid.copy(),
            )
        )
    return cameras
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_views.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add mesh_screenshot/views.py tests/test_views.py
git commit -m "feat: cube camera view generation (6/14/26) with auto-framing"
```

---

## Task 5: Contact-sheet composition

**Files:**
- Create: `mesh_screenshot/contact_sheet.py`
- Test: `tests/test_contact_sheet.py`

**Interfaces:**
- Consumes: `mesh_screenshot.analysis.MeshStats` (Task 3).
- Produces:
  - `grid_dims(n_cells: int) -> tuple[int, int]` — returns `(rows, cols)`, `cols = ceil(sqrt(n))`, `rows = ceil(n / cols)`.
  - `compose_contact_sheet(tiles: list[tuple[str, np.ndarray]], stats: MeshStats, source_name: str, tile_size: tuple[int, int] = (512, 512), background: str = "white") -> PIL.Image.Image`.
    The first grid cell is a text stats panel; each remaining cell is a captioned view tile. Returned image size is `(cols * tile_w, rows * tile_h)`.

- [ ] **Step 1: Write the failing test**

`tests/test_contact_sheet.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_contact_sheet.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mesh_screenshot.contact_sheet'`.

- [ ] **Step 3: Write minimal implementation**

`mesh_screenshot/contact_sheet.py`:
```python
"""Compose rendered view tiles + a stats panel into one contact-sheet PNG."""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .analysis import MeshStats

_CAPTION_H = 18
_FONT = ImageFont.load_default()


def grid_dims(n_cells: int) -> tuple[int, int]:
    """(rows, cols) for a near-square grid holding n_cells."""
    cols = math.ceil(math.sqrt(n_cells))
    rows = math.ceil(n_cells / cols)
    return rows, cols


def _stats_lines(stats: MeshStats, source_name: str) -> list[str]:
    dims = stats.bbox_dims
    return [
        source_name,
        f"vertices: {stats.n_vertices}",
        f"faces: {stats.n_faces}",
        f"watertight: {'yes' if stats.is_watertight else 'no'}",
        f"boundary edges: {stats.n_boundary_edges}",
        f"boundary loops: {stats.n_boundary_loops}",
        f"bbox: {dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f}",
        f"color data: {'yes' if stats.has_color else 'no'}",
    ]


def _panel(size: tuple[int, int], stats: MeshStats, source_name: str,
           background: str) -> Image.Image:
    img = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(img)
    y = 6
    for line in _stats_lines(stats, source_name):
        draw.text((6, y), line, fill="black", font=_FONT)
        y += 14
    draw.rectangle([0, 0, size[0] - 1, size[1] - 1], outline="black")
    return img


def _tile(label: str, arr: np.ndarray, size: tuple[int, int],
          background: str) -> Image.Image:
    img = Image.new("RGB", size, background)
    view = Image.fromarray(np.asarray(arr, dtype=np.uint8)[:, :, :3])
    view = view.resize((size[0], size[1] - _CAPTION_H))
    img.paste(view, (0, _CAPTION_H))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, size[0], _CAPTION_H], fill="black")
    draw.text((4, 3), label, fill="white", font=_FONT)
    return img


def compose_contact_sheet(
    tiles: list[tuple[str, np.ndarray]],
    stats: MeshStats,
    source_name: str,
    tile_size: tuple[int, int] = (512, 512),
    background: str = "white",
) -> Image.Image:
    """Grid = stats panel first, then each captioned view tile."""
    n_cells = len(tiles) + 1
    rows, cols = grid_dims(n_cells)
    tile_w, tile_h = tile_size
    sheet = Image.new("RGB", (cols * tile_w, rows * tile_h), background)

    cells: list[Image.Image] = [_panel(tile_size, stats, source_name, background)]
    for label, arr in tiles:
        cells.append(_tile(label, arr, tile_size, background))

    for idx, cell in enumerate(cells):
        r, c = divmod(idx, cols)
        sheet.paste(cell, (c * tile_w, r * tile_h))
    return sheet
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_contact_sheet.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add mesh_screenshot/contact_sheet.py tests/test_contact_sheet.py
git commit -m "feat: contact-sheet composition with stats panel and captions"
```

---

## Task 6: PyVista offscreen renderer

**Files:**
- Create: `mesh_screenshot/renderer.py`
- Create: `tests/conftest.py`
- Test: `tests/test_renderer.py`

**Interfaces:**
- Consumes: `mesh_screenshot.views.CameraSpec` (Task 4); `mesh_screenshot.errors.RenderBackendError` (Task 1); boundary edges array from `mesh_screenshot.analysis.boundary_edges` (Task 3).
- Produces:
  - `RenderOptions` dataclass: `resolution: tuple[int, int] = (512, 512)`, `show_boundary: bool = True`, `boundary_color: str = "red"`, `boundary_width: float = 4.0`, `wireframe: bool = False`, `background: str = "white"`, `use_color: bool = True`.
  - `render_views(mesh, cameras: list[CameraSpec], options: RenderOptions, boundary_edges: np.ndarray | None = None) -> list[tuple[str, np.ndarray]]` — returns `(label, HxWx3 uint8)` per camera. Raises `RenderBackendError` if offscreen GL is unavailable.

- [ ] **Step 1: Write the failing test**

`tests/conftest.py`:
```python
import pytest


@pytest.fixture(scope="session")
def gl_available() -> bool:
    """True when PyVista can render offscreen in this environment."""
    try:
        import pyvista as pv

        plotter = pv.Plotter(off_screen=True)
        plotter.add_mesh(pv.Sphere())
        plotter.screenshot(return_img=True)
        plotter.close()
        return True
    except Exception:
        return False
```

`tests/test_renderer.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_renderer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mesh_screenshot.renderer'`.

- [ ] **Step 3: Write minimal implementation**

`mesh_screenshot/renderer.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_renderer.py -v`
Expected: PASS on a machine with GL (3 passed); on a headless box without OSMesa the two render tests SKIP and `test_render_options_defaults` passes.

- [ ] **Step 5: Commit**

```bash
git add mesh_screenshot/renderer.py tests/conftest.py tests/test_renderer.py
git commit -m "feat: PyVista offscreen renderer with color, boundary, wireframe"
```

---

## Task 7: CLI wiring and end-to-end

**Files:**
- Create: `mesh_screenshot/cli.py`
- Create: `mesh_screenshot/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `loader.load_mesh` (T2), `analysis.boundary_edges`/`compute_stats`/`mesh_has_color` (T3), `views.generate_cameras`/`VIEW_SETS` (T4), `contact_sheet.compose_contact_sheet` (T5), `renderer.RenderOptions`/`render_views` (T6), all error types (T1).
- Produces:
  - `parse_args(argv: list[str]) -> argparse.Namespace`.
  - `parse_resolution(text: str) -> tuple[int, int]` (accepts `"512x512"`; raises `argparse.ArgumentTypeError` on bad input).
  - `run(args: argparse.Namespace) -> int` (does the work; returns exit code).
  - `main(argv: list[str] | None = None) -> int` (entry point; prints friendly errors).
  - Output files: contact sheet at `<out>/<stem>_contact.png`; with `--individual`, per-view PNGs at `<out>/<stem>_views/<NN>_<label>.png`.

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
import numpy as np
import pytest
import trimesh

from mesh_screenshot.cli import main, parse_args, parse_resolution


def test_parse_resolution_ok():
    assert parse_resolution("640x480") == (640, 480)


def test_parse_resolution_bad():
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        parse_resolution("640-480")


def test_parse_args_defaults():
    args = parse_args(["a.ply"])
    assert args.inputs == ["a.ply"]
    assert args.views == 14
    assert args.boundary is True      # --no-boundary sets this False
    assert args.wireframe is False
    assert args.individual is False


def test_missing_file_exit_code(capsys):
    code = main(["definitely_missing_file.ply", "-o", "out_x"])
    assert code != 0
    err = capsys.readouterr().err
    assert "definitely_missing_file.ply" in err


def test_e2e_contact_sheet(tmp_path, gl_available):
    if not gl_available:
        pytest.skip("no offscreen GL backend available")
    box = trimesh.creation.box(extents=(1, 1, 1))
    mesh_path = tmp_path / "box.ply"
    box.export(mesh_path)
    out = tmp_path / "shots"

    code = main([str(mesh_path), "-o", str(out), "--views", "6",
                 "--resolution", "128x128"])
    assert code == 0
    sheet = out / "box_contact.png"
    assert sheet.exists()

    from PIL import Image

    with Image.open(sheet) as img:
        # 6 views + stats = 7 cells -> 3x3 grid -> 384x384
        assert img.size == (384, 384)


def test_e2e_individual(tmp_path, gl_available):
    if not gl_available:
        pytest.skip("no offscreen GL backend available")
    box = trimesh.creation.box(extents=(1, 1, 1))
    mesh_path = tmp_path / "box.ply"
    box.export(mesh_path)
    out = tmp_path / "shots"

    code = main([str(mesh_path), "-o", str(out), "--views", "6",
                 "--resolution", "64x64", "--individual"])
    assert code == 0
    per_view = list((out / "box_views").glob("*.png"))
    assert len(per_view) == 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mesh_screenshot.cli'`.

- [ ] **Step 3: Write minimal implementation**

`mesh_screenshot/cli.py`:
```python
"""Command-line interface: wire modules and write output files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from . import analysis, contact_sheet, loader, views
from .errors import MeshScreenshotError
from .renderer import RenderOptions, render_views


def parse_resolution(text: str) -> tuple[int, int]:
    try:
        w, h = text.lower().split("x")
        return int(w), int(h)
    except Exception as exc:  # noqa: BLE001
        raise argparse.ArgumentTypeError(
            f"resolution must look like WxH (e.g. 512x512), got '{text}'"
        ) from exc


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="mesh-screenshot",
        description="Render meshes to labeled multi-view contact-sheet PNGs.",
    )
    p.add_argument("inputs", nargs="+", help="Mesh file(s) to render")
    p.add_argument("-o", "--out", default="./mesh_shots",
                   help="Output directory (default: ./mesh_shots)")
    p.add_argument("--views", type=int, choices=views.VIEW_SETS, default=14,
                   help="View set: 6 faces, 14 +corners, 26 +edges")
    p.add_argument("--resolution", type=parse_resolution, default=(512, 512),
                   help="Per-tile render size WxH (default 512x512)")
    p.add_argument("--individual", action="store_true",
                   help="Also write full-res per-view PNGs")
    p.add_argument("--no-boundary", dest="boundary", action="store_false",
                   help="Disable boundary-edge highlight")
    p.add_argument("--boundary-color", default="red",
                   help="Boundary line color (default red)")
    p.add_argument("--wireframe", action="store_true",
                   help="Overlay wireframe")
    p.add_argument("--background", default="white",
                   help="Background color (default white)")
    p.add_argument("--no-color", dest="use_color", action="store_false",
                   help="Ignore mesh colors, use neutral material")
    return p.parse_args(argv)


def _process_one(path: Path, args: argparse.Namespace, out_dir: Path) -> None:
    loaded = loader.load_mesh(path)
    mesh = loaded.mesh
    edges = analysis.boundary_edges(mesh)
    has_color = analysis.mesh_has_color(mesh)
    stats = analysis.compute_stats(mesh, edges, has_color)
    cams = views.generate_cameras(stats.centroid, stats.radius,
                                  view_set=args.views)
    options = RenderOptions(
        resolution=args.resolution,
        show_boundary=args.boundary,
        boundary_color=args.boundary_color,
        wireframe=args.wireframe,
        background=args.background,
        use_color=args.use_color,
    )
    tiles = render_views(mesh, cams, options, edges)

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    sheet = contact_sheet.compose_contact_sheet(
        tiles, stats, path.name, tile_size=args.resolution,
        background=args.background,
    )
    sheet.save(out_dir / f"{stem}_contact.png")

    if args.individual:
        view_dir = out_dir / f"{stem}_views"
        view_dir.mkdir(parents=True, exist_ok=True)
        for idx, (label, arr) in enumerate(tiles):
            Image.fromarray(arr).save(view_dir / f"{idx:02d}_{label}.png")


def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    for raw in args.inputs:
        _process_one(Path(raw), args, out_dir)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return run(args)
    except MeshScreenshotError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
```

`mesh_screenshot/__main__.py`:
```python
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS on a GL machine (6 passed); headless without OSMesa: the two e2e tests SKIP, the 4 arg/error tests pass.

- [ ] **Step 5: Commit**

```bash
git add mesh_screenshot/cli.py mesh_screenshot/__main__.py tests/test_cli.py
git commit -m "feat: CLI wiring, contact-sheet + per-view output, e2e tests"
```

---

## Task 8: Skill layer and README

**Files:**
- Create: `.claude/skills/mesh-screenshot/SKILL.md`
- Create: `README.md`

**Interfaces:**
- Consumes: the finished CLI (`python -m mesh_screenshot`).
- Produces: agent-facing skill doc + human README. No code.

- [ ] **Step 1: Write the SKILL.md**

`.claude/skills/mesh-screenshot/SKILL.md`:
```markdown
---
name: mesh-screenshot
description: Use when you need to SEE a 3D mesh — inspect a .ply/.stl/.obj/.glb file, check a mesh for holes / open boundaries / non-watertightness, verify colors or labels, or confirm a mesh operation produced sane geometry. Renders 14 labeled camera views into one contact-sheet PNG to Read.
---

# Mesh Screenshot

Render any mesh to a single labeled multi-view contact-sheet PNG, then `Read`
the PNG to reason about the geometry.

## When to use

- "What does this mesh/`.ply`/`.stl` look like?"
- "Does this mesh have holes / open edges / is it watertight?"
- "Did this boolean / cleaning / remeshing step break the geometry?"
- Before/after comparison of a mesh-processing operation.

## Recipe

1. Run the tool on the mesh file(s):

   ```bash
   python -m mesh_screenshot <FILE> -o <OUTPUT_DIR>
   ```

2. `Read` the produced contact sheet: `<OUTPUT_DIR>/<stem>_contact.png`.
   It shows a stats panel (vertices, faces, watertight, boundary loops, bbox)
   plus 14 labeled camera views. Boundary/open edges are highlighted in red by
   default — zero highlighted edges means the surface is closed.

## Useful flags

- `--views {6,14,26}` — fewer/more angles (default 14).
- `--wireframe` — overlay mesh edges.
- `--no-boundary` — turn off the red open-edge highlight.
- `--individual` — also write full-res per-view PNGs to `<stem>_views/`.
- `--resolution WxH` — per-tile size (default 512x512).

## Notes

- Colors in the mesh are preserved; uncolored meshes get neutral shading.
- On headless Linux the renderer needs OSMesa or `xvfb-run`; it prints a hint
  if the offscreen backend is missing.
```

- [ ] **Step 2: Write the README**

`README.md`:
```markdown
# mesh-screenshot

Render any 3D mesh to a single labeled **contact-sheet PNG** (14 camera views +
a stats panel) so both humans and AI coding agents can quickly *see* geometry:
holes, open boundaries, colors, and whether an operation produced something sane.

## Install

```bash
pip install -e .
```

Dependencies: `trimesh`, `pyvista`, `numpy`, `pillow`.

## Usage

```bash
python -m mesh_screenshot model.ply -o shots/
python -m mesh_screenshot model.stl -o shots/ --views 26 --wireframe
python -m mesh_screenshot a.ply b.obj -o shots/ --individual
```

Output: `shots/<name>_contact.png` (and `shots/<name>_views/*.png` with
`--individual`).

| Flag | Default | Meaning |
|------|---------|---------|
| `-o, --out DIR` | `./mesh_shots` | Output directory |
| `--views {6,14,26}` | `14` | View set (faces / +corners / +edges) |
| `--resolution WxH` | `512x512` | Per-tile render size |
| `--individual` | off | Also write per-view PNGs |
| `--no-boundary` | boundary on | Disable open-edge highlight |
| `--boundary-color` | `red` | Boundary line color |
| `--wireframe` | off | Overlay wireframe |
| `--background` | `white` | Background color |
| `--no-color` | colors on | Ignore mesh colors |

## Headless / CI

PyVista offscreen rendering works natively on Windows/macOS and on Linux with a
GPU or OSMesa. On a headless Linux box, run under a virtual display:

```bash
xvfb-run python -m mesh_screenshot model.ply -o shots/
```

## Development

```bash
pip install -e ".[test]"
python -m pytest -v
```
```

- [ ] **Step 3: Verify the tool runs end-to-end**

Run:
```bash
python -c "import trimesh; trimesh.creation.box(extents=(1,1,1)).export('._smoke.ply')"
python -m mesh_screenshot ._smoke.ply -o ._smoke_out
```
Expected: exits 0; `._smoke_out/._smoke_contact.png` exists (skip/ignore if the
machine has no GL backend — the earlier unit tests already cover non-GL logic).
Clean up: `rm ._smoke.ply; rm -r ._smoke_out` (PowerShell: `Remove-Item ._smoke.ply, ._smoke_out -Recurse -Force`).

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/mesh-screenshot/SKILL.md README.md
git commit -m "docs: add mesh-screenshot skill and README"
```

---

## Dependency graph (for parallel execution)

```
Task 1 (scaffold)
  ├─> Task 2 (loader)      ┐
  ├─> Task 3 (analysis)    ├─ independent, can run in parallel
  └─> Task 4 (views)       ┘
Task 3 ─> Task 5 (contact_sheet)
Task 3 + Task 4 ─> Task 6 (renderer)
Tasks 2..6 ─> Task 7 (cli)
Task 7 ─> Task 8 (skill + README)
```

## Self-review notes

- **Spec coverage:** loader→§3; boundary edges/stats→§3/§5; 14-view cube + auto-framing→§4; colors/boundary/wireframe/background/stats panel→§5; 4×4 grid + captions + resolution + `--individual`→§6; every CLI flag in §7 mapped in Task 7; skill→§8; deps→§9; unit + GL-guarded + e2e tests→§10.
- **Type consistency:** `MeshStats`(T3) consumed by T5/T7; `CameraSpec`(T4) by T6/T7; `RenderOptions`(T6) by T7; `boundary_edges`→ndarray shared T3→T6→T7; error types from T1 used everywhere.
- **No placeholders:** every code step is complete and runnable.
```

