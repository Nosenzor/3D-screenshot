# Mesh Screenshot — Design Spec

- **Date:** 2026-07-24
- **Status:** Approved (design), pending implementation plan
- **Author:** Romain Nosenzo (with Claude Code)
- **Repo:** `3D-screenshot`

## 1. Context & goal

AI coding agents cannot "see" 3D meshes. When working with mesh-processing code
(loading, cleaning, segmentation, boolean ops, tray/splint/model generation),
the agent is blind to what the geometry actually looks like — whether a mesh has
holes, whether colors/segmentation are correct, whether an operation produced a
degenerate result.

**Goal:** a small, standalone tool that renders any mesh to a single labeled
**contact-sheet PNG** showing 14 camera angles, so an agent can run one command,
`Read` one image, and reason about the geometry. Colors are preserved, boundary
(open) edges are highlighted, and a wireframe overlay is optional.

This is a fresh, generic tool. It is *not* coupled to the dental pipeline, but it
ships an opt-in **dental preset** that reproduces the conventions used in the
dental repo's existing renderer.

### Reference (prior art, not reused directly)

`dental_processing_pipelines/scripts/compare_versions/image_exporter.py` is the
proven renderer this design draws from. Key lessons carried over:

- trimesh loads meshes and reads colors; **PyVista (VTK) does the actual
  rendering** (`pv.Plotter(off_screen=True)` → `plotter.screenshot()`).
- Colors are pushed to PyVista as cell data with `rgb=True`
  (`add_segmentation` in the reference).
- Cameras are orbited around the mesh centroid at multiple angles.
- The dental convention: per-jaw normals (`lower=[0,1,0]`, `upper=[0,-1,0]`),
  view-up (`lower=[0,0,1]`, `upper=[0,0,-1]`), angled orbits at
  `angle∈{50,90}`, `theta∈{0,135,270}`.

`generate_local_report.py` is *not* a rendering reference — it only builds
summary tables/charts from `summary.json`.

## 2. Decisions (locked)

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Deliverable form | **Skill over a CLI core** | Lightest, portable, versioned in-repo, transparent. No long-running process. The rendering core is a plain CLI, so a future MCP server is a thin wrapper over the same code. |
| 2 | Rendering backend | **trimesh + PyVista** | trimesh for I/O + geometry/color/boundary analysis; PyVista for reliable headless rendering with easy wireframe + edge overlays and clean cameras. Matches proven `image_exporter.py`. |
| 3 | Scope & location | **Generic in `3D-screenshot`, with an opt-in dental preset** | Reusable on any mesh; dental conventions available via `--preset dental`. |
| 4 | Image output | **Contact sheet by default; optional per-view PNGs** | One tiled image = one `Read`, all angles at once, token-efficient. `--individual` dumps full-res per-view files when needed. |

**MCP explicitly deferred** (not built now): the CLI core stays factored so an
MCP server wrapping it remains a small future addition.

## 3. Architecture

Python package `mesh_screenshot/`, invoked as `python -m mesh_screenshot`.
Units are isolated so everything except `renderer.py` is testable without a GPU
or display.

| Module | Responsibility | Inputs → Outputs | Needs GL? |
|--------|----------------|------------------|-----------|
| `loader.py` | Load mesh; flatten `trimesh.Scene` → single mesh; handle point clouds | path → `Trimesh`/`PointCloud` + source metadata | No |
| `analysis.py` | Geometry facts: boundary edges (edges used by exactly one face), watertight flag, vertex/face counts, bbox dims, centroid, bounding-sphere radius | mesh → `MeshStats` | No |
| `views.py` | Camera generation: 14 cube directions → auto-framed camera positions + up-vectors from mesh bounds; presets for 6/14/26 | bounds + view-set → list of `CameraSpec` | No |
| `renderer.py` | **Only** PyVista code: render one mesh + one camera + options → RGB image array (colors, boundary lines, wireframe, background) | mesh + `CameraSpec` + `RenderOptions` → `np.ndarray` | Yes |
| `contact_sheet.py` | Compose tiled sheet: view images + per-tile labels + stats panel → one PNG (PIL) | list of (label, image) + `MeshStats` → PNG | No |
| `presets.py` | `generic` vs `dental` view sets, orientation, and color handling | preset name + mesh → view/orientation config | No |
| `cli.py` / `__main__.py` | argparse, wire modules, write output files, error reporting | argv → files on disk + exit code | No |

**Boundary edge definition:** an edge referenced by exactly one face. In trimesh:
group `mesh.edges_sorted` and keep rows with count 1. A watertight mesh has zero
boundary edges — so the highlight doubles as an instant "is this closed?" signal.

## 4. The 14-view system

Directions on a unit cube, camera looking at the mesh centroid:

- **6 face normals:** `+X, -X, +Y, -Y, +Z, -Z`
- **8 corner diagonals:** `(±1, ±1, ±1)` (normalized)
- Total = **14**, each labeled on its tile (e.g. `+X`, `+X+Y+Z`).

`--views {6,14,26}`: `6` = faces only; `14` = faces + corners (default);
`26` = adds the 12 edge midpoints.

**Auto-framing:** camera distance is derived from the mesh's bounding-sphere
radius and a fixed vertical FOV so the mesh fills each frame regardless of its
absolute scale (critical for a generic tool that does not know mesh units).

## 5. Rendering behavior

- **Colors preserved:** if the mesh has vertex or face colors, render them via
  PyVista `rgb=True` (as in the reference `add_segmentation`). If it has none,
  fall back to a neutral lit material; note "no color data" on the sheet.
- **Boundary edges (headline feature):** computed in `analysis.py`, drawn as
  thick colored lines over the surface. **On by default.** `--no-boundary`
  disables; `--boundary-color` sets the color (default red).
- **Wireframe:** `--wireframe` overlays mesh edges (`show_edges`); **off by
  default.**
- **Background:** `--background` (default white).
- **Stats panel** rendered onto the sheet: filename, #vertices, #faces,
  watertight yes/no, #boundary loops, bbox dimensions. Cheap metadata that helps
  the model reason, not just look.

## 6. Contact sheet layout

- A **4×4 grid** (16 cells): one title/stats panel + the 14 labeled view tiles,
  leaving one spare cell (used for extra stats or left blank). The 6-view set
  uses a smaller grid; the 26-view set a larger one.
- Each tile captioned with its view label.
- Default per-tile render resolution 512×512 (`--resolution WxH`).
- Default output: **only the contact sheet** is written. `--individual` also
  writes full-res per-view PNGs alongside it.

## 7. CLI interface

```
python -m mesh_screenshot INPUT [INPUT ...] [options]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `-o, --out DIR` | `./mesh_shots` | Output directory |
| `--views {6,14,26}` | `14` | View set |
| `--preset {generic,dental}` | `generic` | Rendering preset |
| `--resolution WxH` | `512x512` | Per-tile render size |
| `--individual` | off | Also write per-view PNGs |
| `--no-boundary` | (boundary on) | Disable boundary-edge highlight |
| `--boundary-color COLOR` | `red` | Boundary line color |
| `--wireframe` | off | Overlay wireframe |
| `--background COLOR` | `white` | Background color |
| `--no-color` | (colors on) | Ignore mesh colors, use neutral material |
| `--area {upper,lower}` | (none) | Dental preset: which jaw (orientation) |

Example:

```bash
python -m mesh_screenshot model.ply -o shots/ --views 14 --wireframe
```

Exit non-zero with a clear message on failure (see §10).

## 8. Dental preset

A thin layer over the same engine, selected with `--preset dental`:

- Orients the mesh to the occlusal plane and uses per-jaw normals/up-vectors
  (`--area upper|lower`), echoing `image_exporter.py`.
- Uses a curated view set: occlusal top/bottom + angled orbits
  (`angle∈{50,90}`, `theta∈{0,135,270}`) instead of the generic cube.
- Expects segmentation face-colors and renders them as-is.

Generic remains the default; dental is entirely opt-in.

## 9. Skill layer

`.claude/skills/mesh-screenshot/SKILL.md`:

- **When to use** triggers: "see / inspect / visualize a mesh", "check a mesh
  for holes / boundaries / open edges", "what does this `.ply`/`.stl`/`.obj`
  look like".
- **Recipe:** run `python -m mesh_screenshot <file> -o <dir>`, then `Read` the
  produced contact-sheet PNG.
- Notes the key flags (`--wireframe`, `--views`, `--preset dental`,
  `--individual`).

## 10. Dependencies & environment

- **Runtime deps:** `trimesh`, `pyvista`, `numpy`, `pillow`.
- PyVista offscreen rendering works natively on Windows 11 (target dev machine).
- On headless Linux/CI, offscreen VTK needs OSMesa or a virtual display
  (`xvfb-run`); the tool detects a failed GL context and prints an actionable
  hint rather than a raw stack trace.

## 11. Testing strategy

- **Unit (no GL):**
  - `analysis.py`: an open plane / a mesh with a known hole → expected boundary
    edge count; a closed cube → 0 boundary edges; watertight flag correct.
  - `views.py`: 14/6/26 direction counts, labels, and auto-framed distances for
    known bounds.
  - `contact_sheet.py`: composition produces an image of the expected size from
    dummy tiles + stats.
- **Render smoke test (guarded/skipped if no GL):** render a simple mesh
  offscreen and assert a non-blank array of the expected shape.
- **CLI e2e:** run against a tiny bundled sample mesh; assert the contact-sheet
  file is created with expected dimensions; assert `--individual` adds per-view
  files.

## 12. Out of scope (YAGNI)

- Curvature / distance heatmap coloring.
- Animation / GIF / turntable output.
- Interactive viewer.
- The MCP server wrapper (core kept ready for it, but not built now).

## 13. Open questions

None blocking. Minor choices (exact spare-cell usage in the 4×4 grid, exact
neutral material shading) are left to implementation discretion.
