"""Exception types shared across the package."""


class MeshScreenshotError(Exception):
    """Base class for all mesh_screenshot errors."""


class MeshLoadError(MeshScreenshotError):
    """Raised when an input file cannot be loaded as a mesh."""


class RenderBackendError(MeshScreenshotError):
    """Raised when the offscreen GL/render backend is unavailable."""
