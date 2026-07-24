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
