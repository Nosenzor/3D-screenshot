import os

import pytest

#: Set this to 1/true/yes to turn "no GL backend" from a skip into a failure.
#: CI sets it on at least one platform so a rendering regression cannot hide
#: behind silently skipped tests.
REQUIRE_GL_ENV = "MESH_SCREENSHOT_REQUIRE_GL"


def _probe_gl() -> tuple[bool, str]:
    """Try a real offscreen render. Returns (ok, reason_if_not_ok)."""
    plotter = None
    try:
        import pyvista as pv

        plotter = pv.Plotter(off_screen=True)
        plotter.add_mesh(pv.Sphere())
        plotter.screenshot(return_img=True)
        return True, ""
    except Exception as exc:  # noqa: BLE001 - any failure means "no usable GL"
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        if plotter is not None:
            try:
                plotter.close()
            except Exception:  # noqa: BLE001
                pass


def gl_is_required(environ=None) -> bool:
    """True when the caller demanded that offscreen GL actually work."""
    env = os.environ if environ is None else environ
    return env.get(REQUIRE_GL_ENV, "").strip().lower() in ("1", "true", "yes")


def resolve_gl_available(probe=_probe_gl, environ=None) -> bool:
    """Decide whether GL is usable, failing the run when GL was required.

    Split out from the fixture so the gate itself is testable: a silently
    broken gate would stop protecting CI without anyone noticing.
    """
    ok, reason = probe()
    if not ok and gl_is_required(environ):
        pytest.fail(
            f"{REQUIRE_GL_ENV} is set but offscreen rendering is unavailable: "
            f"{reason}"
        )
    return ok


@pytest.fixture(scope="session")
def gl_available() -> bool:
    """True when PyVista can render offscreen in this environment.

    Honors ``MESH_SCREENSHOT_REQUIRE_GL``: when set, a missing backend fails
    the run instead of skipping, so CI proves the render path was exercised.
    """
    return resolve_gl_available()
