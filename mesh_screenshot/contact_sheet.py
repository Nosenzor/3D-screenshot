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
        f"boundary components: {stats.n_boundary_components}",
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


def _caption_height(tile_h: int) -> int:
    """Caption bar height, shrunk so a very short tile still leaves 1px of view."""
    return max(1, min(_CAPTION_H, tile_h - 1))


def _tile(label: str, arr: np.ndarray, size: tuple[int, int],
          background: str) -> Image.Image:
    img = Image.new("RGB", size, background)
    cap_h = _caption_height(size[1])
    view = Image.fromarray(np.asarray(arr, dtype=np.uint8)[:, :, :3])
    view = view.resize((max(1, size[0]), max(1, size[1] - cap_h)))
    img.paste(view, (0, cap_h))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, size[0], cap_h], fill="black")
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
