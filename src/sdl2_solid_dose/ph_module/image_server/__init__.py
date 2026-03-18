from .server import CameraServer

# Backward-compatible alias for previous naming.
ImageServer = CameraServer

__all__ = ["CameraServer", "ImageServer"]
