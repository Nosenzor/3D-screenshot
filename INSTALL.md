# Installing mesh-screenshot

`mesh-screenshot` renders any mesh to a labeled multi-view contact-sheet PNG.
It needs a working **offscreen OpenGL** backend, which is the only part of
installation that ever causes trouble — see [Platform notes](#platform-notes).

- [Requirements](#requirements)
- [Install](#install)
- [Verify the install](#verify-the-install)
- [Platform notes](#platform-notes)
- [Using it from other projects](#using-it-from-other-projects)
- [Installing the Claude Code skill](#installing-the-claude-code-skill)
- [Running the tests](#running-the-tests)
- [Troubleshooting](#troubleshooting)
- [Uninstall](#uninstall)

## Requirements

| | |
|---|---|
| Python | 3.10 or newer |
| Runtime dependencies | `trimesh`, `pyvista`, `numpy`, `pillow` (installed automatically) |
| Graphics | An offscreen OpenGL 3.2+ context. Works out of the box on Windows and macOS; headless Linux needs one extra step. |
| Disk | ~250 MB, mostly VTK (pulled in by PyVista) |

Verified on Python 3.11 with numpy 2.3–2.4, trimesh 4.11–4.12, pyvista 0.48,
pillow 12. CI covers Python 3.10–3.13 on Linux, Windows, and macOS.

## Install

Use a virtual environment unless you have a reason not to.

### From a clone (recommended for development)

```bash
git clone https://github.com/Nosenzor/3D-screenshot.git
cd 3D-screenshot
python -m venv .venv
```

Activate it — on Linux/macOS:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Then install in editable mode:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

Add the test extra if you plan to run the suite:

```bash
python -m pip install -e ".[test]"
```

### Directly from GitHub

No clone needed:

```bash
python -m pip install "git+https://github.com/Nosenzor/3D-screenshot.git"
```

### From a built wheel

```bash
python -m pip install --upgrade build
python -m build
```

That writes `dist/mesh_screenshot-<version>-py3-none-any.whl`. Install it into
any environment:

```bash
python -m pip install dist/mesh_screenshot-0.1.0-py3-none-any.whl
```

## Verify the install

Both entry points are equivalent — the console script is on `PATH` after
install, the module form always works:

```bash
mesh-screenshot --help
```

```bash
python -m mesh_screenshot --help
```

Render a generated test sphere end to end:

```bash
python -c "import trimesh; trimesh.creation.icosphere(subdivisions=2, radius=5.0).export('smoke.ply')"
```

```bash
mesh-screenshot smoke.ply -o shots --views 6 --resolution 128x128
```

That writes `shots/smoke_contact.png`. Confirm it is the right size and is not
blank — this catches a silently broken GL backend, which otherwise produces an
all-white sheet with exit code 0:

```bash
python scripts/check_contact_sheet.py shots/smoke_contact.png --expect-size 384x384
```

Expected output:

```
OK: smoke_contact.png size=(384, 384) non-white pixels=71630
```

The exact pixel count varies slightly by platform and driver; anything
comfortably above zero means real geometry was rendered.

## Platform notes

### Windows and macOS

Nothing extra. Offscreen rendering works with the default OpenGL
implementation.

### Linux with a desktop or GPU

Nothing extra, as long as OpenGL 3.2+ is available.

### Headless Linux, containers, CI

VTK still needs a GL context with no display attached. Two options.

**Option A — a virtual display (simplest).** Install Xvfb plus the GL runtime
libraries, then run the tool under `xvfb-run`:

```bash
sudo apt-get update && sudo apt-get install -y xvfb libgl1 libglx-mesa0 libxrender1 libxext6
```

```bash
xvfb-run -a mesh-screenshot model.ply -o shots/
```

On older Ubuntu releases the GL package is named `libgl1-mesa-glx` instead of
`libgl1 libglx-mesa0`. Install whichever your distro provides.

**Option B — software rendering with OSMesa.** No X server at all; install a
PyVista build wired to OSMesa, per the
[PyVista headless documentation](https://docs.pyvista.org/getting-started/installation.html).
Prefer this for long-running services where starting Xvfb is awkward.

If neither is available, the tool exits non-zero with an actionable message
rather than a stack trace:

```
error: Offscreen rendering failed. On headless Linux, install OSMesa or run
under a virtual display, e.g. `xvfb-run python -m mesh_screenshot ...`.
```

### Docker

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb libgl1 libglx-mesa0 libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "git+https://github.com/Nosenzor/3D-screenshot.git"
ENTRYPOINT ["xvfb-run", "-a", "mesh-screenshot"]
```

```bash
docker build -t mesh-screenshot .
docker run --rm -v "$PWD:/work" -w /work mesh-screenshot model.ply -o shots/
```

## Using it from other projects

`python -m mesh_screenshot` only resolves if the package is importable in the
active environment. Running it from an unrelated directory without installing
it will fail with `No module named mesh_screenshot`.

To use it while working in another repository, install it into **that**
project's environment. An editable install points at your clone, so edits here
take effect there immediately:

```bash
python -m pip install -e /path/to/3D-screenshot
```

Or install it non-editable from GitHub:

```bash
python -m pip install "git+https://github.com/Nosenzor/3D-screenshot.git"
```

Either way `mesh-screenshot` and `python -m mesh_screenshot` then work from any
working directory.

## Installing the Claude Code skill

The repo ships an agent-facing skill at
`.claude/skills/mesh-screenshot/SKILL.md`. Claude Code picks it up
automatically when working **inside this repo**.

To make it available in every project, copy it into your user-level skills
directory. Linux/macOS:

```bash
mkdir -p ~/.claude/skills && cp -r .claude/skills/mesh-screenshot ~/.claude/skills/
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME\.claude\skills" | Out-Null
Copy-Item -Recurse -Force ".claude\skills\mesh-screenshot" "$HOME\.claude\skills\"
```

The skill shells out to `python -m mesh_screenshot`, so the package must also
be installed in the environment the agent uses — see
[Using it from other projects](#using-it-from-other-projects).

## Running the tests

```bash
python -m pip install -e ".[test]"
python -m pytest tests/ -v
```

Expect **47 passed**. Render tests skip automatically when no GL backend is
present, so a green run does not by itself prove rendering works. To make a
missing backend a failure instead of a skip — what CI does — set:

```bash
MESH_SCREENSHOT_REQUIRE_GL=1 python -m pytest tests/ -v -rs
```

On Windows PowerShell:

```powershell
$env:MESH_SCREENSHOT_REQUIRE_GL = "1"; python -m pytest tests/ -v -rs
```

Use `-rs` to print the reason for every skip.

## Troubleshooting

**`No module named mesh_screenshot`** — the package is not installed in the
active interpreter. Check with `python -c "import mesh_screenshot, sys; print(sys.executable)"`
and re-run the install for that interpreter.

**`mesh-screenshot: command not found` after a successful install** — the
script directory is not on `PATH`. Use `python -m mesh_screenshot` instead,
which never depends on `PATH`.

**All tiles are blank / the sheet is pure white** — the GL backend is not
producing frames. Run the checker in
[Verify the install](#verify-the-install); if it reports the sheet is blank,
follow [Headless Linux](#headless-linux-containers-ci).

**`error: Offscreen rendering failed`** — expected when no GL context exists.
Install Xvfb or OSMesa as above.

**`error: resolution must be at least 32x32`** — `--resolution` was too small
for a legible tile. Pass something like `--resolution 512x512`.

**Renders are slow on a large mesh** — cost scales with view count. Use
`--views 6` for a quick look and drop `--resolution`; the default writes 14
views at 512×512.

**A warning about several inputs sharing a name** — two inputs have the same
filename stem, so outputs would collide. The tool disambiguates
(`model_contact.png`, `model_2_contact.png`) instead of overwriting. Pass
separate `-o` directories if you want the original names.

## Uninstall

```bash
python -m pip uninstall mesh-screenshot
```
