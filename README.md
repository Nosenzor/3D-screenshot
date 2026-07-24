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
