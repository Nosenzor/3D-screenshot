#!/usr/bin/env python3
"""Assert a rendered contact sheet exists, has the expected size, and is not blank.

Used by CI to prove an installed build really renders something, but it is a
plain script so you can run the same check locally:

    python scripts/check_contact_sheet.py shots/smoke_contact.png --expect-size 384x384
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def parse_size(text: str) -> tuple[int, int]:
    w, h = text.lower().split("x")
    return int(w), int(h)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to the contact-sheet PNG")
    parser.add_argument("--expect-size", type=parse_size, default=None,
                        help="Required pixel size, e.g. 384x384")
    parser.add_argument("--min-nonwhite", type=int, default=1000,
                        help="Minimum non-white pixels (default 1000)")
    args = parser.parse_args(argv)

    if not args.path.is_file():
        print(f"FAIL: no contact sheet at {args.path}", file=sys.stderr)
        return 1

    with Image.open(args.path) as img:
        rgb = img.convert("RGB")
        size = rgb.size
        arr = np.asarray(rgb)

    if args.expect_size and size != args.expect_size:
        print(f"FAIL: expected size {args.expect_size}, got {size}", file=sys.stderr)
        return 1

    nonwhite = int((arr.min(axis=2) < 250).sum())
    if nonwhite < args.min_nonwhite:
        print(
            f"FAIL: sheet looks blank ({nonwhite} non-white pixels, "
            f"need >= {args.min_nonwhite}). The renderer probably produced "
            "empty frames.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {args.path.name} size={size} non-white pixels={nonwhite}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
