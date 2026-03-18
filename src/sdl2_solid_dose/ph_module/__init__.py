from .image_req_client import PHAnalyzer, pHAnalyzer, ph_from_image

# image_server depends on picamera2 (Raspberry Pi runtime). Keep it optional so
# client-only workflows can run on non-Pi environments.
try:
    from .image_server import CameraServer, ImageServer
except ModuleNotFoundError:
    CameraServer = None
    ImageServer = None

__all__ = [
    "PHAnalyzer",
    "pHAnalyzer",
    "ph_from_image",
]

if CameraServer is not None:
    __all__.extend(["CameraServer", "ImageServer"])