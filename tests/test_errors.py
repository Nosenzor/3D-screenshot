import mesh_screenshot
from mesh_screenshot.errors import (
    MeshScreenshotError,
    MeshLoadError,
    RenderBackendError,
)


def test_version_is_string():
    assert isinstance(mesh_screenshot.__version__, str)
    assert mesh_screenshot.__version__


def test_error_hierarchy():
    assert issubclass(MeshLoadError, MeshScreenshotError)
    assert issubclass(RenderBackendError, MeshScreenshotError)
    assert issubclass(MeshScreenshotError, Exception)
