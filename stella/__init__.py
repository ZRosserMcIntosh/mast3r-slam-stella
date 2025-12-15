"""
Stella World Package - A portable 3D world format for explorable spaces.

.stella files are ZIP containers with:
- manifest.json (required)
- levels/<n>/level.json (required per level)
- levels/<n>/render.glb (required per level)
- levels/<n>/collision.rlevox (required per level)
- Optional: navmesh, semantics, thumbnails, checksums
"""

__version__ = "0.1.0"

from stella.package import pack_stella, unpack_stella, get_stella_info, validate_stella
from stella.manifest import make_manifest, make_level_json, Manifest, LevelJson
from stella.vox_rle import write_rlevox, read_rlevox

__all__ = [
    "pack_stella",
    "unpack_stella",
    "get_stella_info",
    "validate_stella",
    "make_manifest",
    "make_level_json",
    "Manifest",
    "LevelJson",
    "write_rlevox",
    "read_rlevox",
]