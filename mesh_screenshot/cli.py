"""Command-line interface: wire modules and write output files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from . import analysis, contact_sheet, loader, views
from .errors import MeshScreenshotError
from .renderer import RenderOptions, render_views


MIN_TILE = 32


def parse_resolution(text: str) -> tuple[int, int]:
    try:
        w_text, h_text = text.lower().split("x")
        w, h = int(w_text), int(h_text)
    except Exception as exc:  # noqa: BLE001
        raise argparse.ArgumentTypeError(
            f"resolution must look like WxH (e.g. 512x512), got '{text}'"
        ) from exc
    if w < MIN_TILE or h < MIN_TILE:
        raise argparse.ArgumentTypeError(
            f"resolution must be at least {MIN_TILE}x{MIN_TILE}, got '{text}'"
        )
    return w, h


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


def _process_one(path: Path, args: argparse.Namespace, out_dir: Path,
                 out_stem: str) -> None:
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
    sheet = contact_sheet.compose_contact_sheet(
        tiles, stats, path.name, tile_size=args.resolution,
        background=args.background,
    )
    sheet.save(out_dir / f"{out_stem}_contact.png")

    if args.individual:
        view_dir = out_dir / f"{out_stem}_views"
        view_dir.mkdir(parents=True, exist_ok=True)
        for idx, (label, arr) in enumerate(tiles):
            Image.fromarray(arr).save(view_dir / f"{idx:02d}_{label}.png")


def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    seen: dict[str, int] = {}
    for raw in args.inputs:
        path = Path(raw)
        stem = path.stem
        count = seen.get(stem, 0)
        seen[stem] = count + 1
        out_stem = stem if count == 0 else f"{stem}_{count + 1}"
        if count:
            print(
                f"warning: several inputs share the name '{stem}'; writing "
                f"'{out_stem}_contact.png' so earlier output is not overwritten",
                file=sys.stderr,
            )
        _process_one(path, args, out_dir, out_stem)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return run(args)
    except MeshScreenshotError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - never surface a raw traceback
        print(f"error: unexpected failure ({type(exc).__name__}): {exc}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
