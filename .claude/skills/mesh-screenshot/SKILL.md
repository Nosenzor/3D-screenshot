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
   It shows a stats panel (vertices, faces, watertight, boundary edges,
   boundary components, bbox) plus 14 labeled camera views. Boundary/open edges
   are highlighted in red by default — zero highlighted edges means the surface
   is closed.

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
