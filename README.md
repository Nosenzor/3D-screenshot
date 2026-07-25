# mesh-screenshot

[![CI](https://github.com/Nosenzor/3D-screenshot/actions/workflows/ci.yml/badge.svg)](https://github.com/Nosenzor/3D-screenshot/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)

Render any 3D mesh to a single labeled **contact-sheet PNG** (14 camera views +
a stats panel) so both humans and AI coding agents can quickly *see* geometry:
holes, open boundaries, colors, and whether an operation produced something sane.

## Install

```bash
pip install -e .
```

Or without cloning:

```bash
pip install "git+https://github.com/Nosenzor/3D-screenshot.git"
```

Dependencies: `trimesh`, `pyvista`, `numpy`, `pillow`. Python 3.10+.

See **[INSTALL.md](INSTALL.md)** for virtualenvs, wheels, Docker, headless
Linux setup, installing the Claude Code skill globally, and troubleshooting.

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

Render tests skip silently when no GL backend is present, so set
`MESH_SCREENSHOT_REQUIRE_GL=1` to turn a missing backend into a failure:

```bash
MESH_SCREENSHOT_REQUIRE_GL=1 python -m pytest tests/ -v -rs
```

CI runs the suite on Linux, Windows, and macOS across Python 3.10–3.13, plus a
strict Linux job where rendering is required and no test may skip, and a
packaging job that installs the built wheel into a clean venv and renders with
the documented command.
