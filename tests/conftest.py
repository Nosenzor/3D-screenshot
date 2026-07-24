import pytest


@pytest.fixture(scope="session")
def gl_available() -> bool:
    """True when PyVista can render offscreen in this environment."""
    try:
        import pyvista as pv

        plotter = pv.Plotter(off_screen=True)
        plotter.add_mesh(pv.Sphere())
        plotter.screenshot(return_img=True)
        plotter.close()
        return True
    except Exception:
        return False
