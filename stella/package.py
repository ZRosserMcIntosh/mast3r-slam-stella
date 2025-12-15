"""
Pack and unpack .stella files (ZIP containers).

.stella files are ZIP archives with deterministic ordering and optional checksums.
"""

import zipfile
import hashlib
import json
from pathlib import Path
from typing import Dict, Union, Tuple, Optional, List
from io import BytesIO

from stella.manifest import Manifest, LevelJson


def compute_sha256(data: bytes) -> str:
    """Compute SHA256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()


def pack_stella(
    output_path: Union[str, Path],
    manifest: Union[Manifest, Dict],
    file_map: Dict[str, bytes],
    include_checksums: bool = True,
) -> Path:
    """
    Pack a .stella file from manifest and file contents.
    
    Args:
        output_path: Path for output .stella file
        manifest: Manifest object or dict
        file_map: Dict mapping archive paths to file bytes
                  e.g. {"levels/0/render.glb": <bytes>, ...}
        include_checksums: Whether to include checksums.sha256
    
    Returns:
        Path to created .stella file
    
    Example:
        >>> manifest = make_manifest(title="My World")
        >>> files = {
        ...     "levels/0/level.json": level_json.to_json().encode(),
        ...     "levels/0/render.glb": glb_bytes,
        ...     "levels/0/collision.rlevox": vox_bytes,
        ... }
        >>> pack_stella("output.stella", manifest, files)
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert manifest to JSON bytes
    if isinstance(manifest, Manifest):
        manifest_bytes = manifest.to_json().encode("utf-8")
    else:
        manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
    
    # Build complete file map with manifest
    all_files: Dict[str, bytes] = {"manifest.json": manifest_bytes}
    all_files.update(file_map)
    
    # Generate checksums if requested
    checksums: Dict[str, str] = {}
    if include_checksums:
        for path, data in sorted(all_files.items()):
            checksums[path] = compute_sha256(data)
        
        # Create checksums file content
        checksum_lines = [f"{hash}  {path}" for path, hash in sorted(checksums.items())]
        all_files["checksums.sha256"] = "\n".join(checksum_lines).encode("utf-8")
    
    # Sort paths for deterministic output
    sorted_paths = sorted(all_files.keys())
    
    # Ensure manifest.json is first, checksums.sha256 is last
    if "manifest.json" in sorted_paths:
        sorted_paths.remove("manifest.json")
        sorted_paths.insert(0, "manifest.json")
    if "checksums.sha256" in sorted_paths:
        sorted_paths.remove("checksums.sha256")
        sorted_paths.append("checksums.sha256")
    
    # Create ZIP
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted_paths:
            zf.writestr(path, all_files[path])
    
    return output_path


def unpack_stella(
    stella_path: Union[str, Path],
    extract_to: Optional[Union[str, Path]] = None,
) -> Tuple[Manifest, zipfile.ZipFile]:
    """
    Open and validate a .stella file.
    
    Args:
        stella_path: Path to .stella file
        extract_to: Optional directory to extract all files to
    
    Returns:
        Tuple of (Manifest, ZipFile handle)
        Note: Caller should close ZipFile when done, or use as context manager
    
    Raises:
        ValueError: If manifest.json is missing or invalid
    """
    stella_path = Path(stella_path)
    
    zf = zipfile.ZipFile(stella_path, "r")
    
    # Read and parse manifest
    if "manifest.json" not in zf.namelist():
        zf.close()
        raise ValueError("Invalid .stella file: missing manifest.json")
    
    manifest_bytes = zf.read("manifest.json")
    manifest = Manifest.from_json(manifest_bytes.decode("utf-8"))
    
    # Optionally extract
    if extract_to:
        extract_to = Path(extract_to)
        extract_to.mkdir(parents=True, exist_ok=True)
        zf.extractall(extract_to)
    
    return manifest, zf


def read_stella_file(
    stella_path: Union[str, Path],
    internal_path: str,
) -> bytes:
    """
    Read a single file from a .stella archive.
    
    Args:
        stella_path: Path to .stella file
        internal_path: Path within archive (e.g. "levels/0/render.glb")
    
    Returns:
        File contents as bytes
    """
    with zipfile.ZipFile(stella_path, "r") as zf:
        return zf.read(internal_path)


def get_stella_info(stella_path: Union[str, Path]) -> Dict:
    """
    Get summary information about a .stella file.
    
    Args:
        stella_path: Path to .stella file
    
    Returns:
        Dict with manifest, file list, and sizes
    """
    stella_path = Path(stella_path)
    
    with zipfile.ZipFile(stella_path, "r") as zf:
        manifest_bytes = zf.read("manifest.json")
        manifest = Manifest.from_json(manifest_bytes.decode("utf-8"))
        
        files = []
        total_size = 0
        for info in zf.infolist():
            files.append({
                "path": info.filename,
                "compressed_size": info.compress_size,
                "uncompressed_size": info.file_size,
            })
            total_size += info.file_size
        
        return {
            "manifest": manifest.to_dict(),
            "files": files,
            "total_uncompressed_size": total_size,
            "archive_size": stella_path.stat().st_size,
        }


def verify_stella_checksums(stella_path: Union[str, Path]) -> Tuple[bool, List[str]]:
    """
    Verify checksums in a .stella file.
    
    Args:
        stella_path: Path to .stella file
    
    Returns:
        Tuple of (all_valid, list_of_errors)
    """
    errors = []
    
    with zipfile.ZipFile(stella_path, "r") as zf:
        if "checksums.sha256" not in zf.namelist():
            return True, ["No checksums.sha256 file found (not an error)"]
        
        checksum_content = zf.read("checksums.sha256").decode("utf-8")
        
        for line in checksum_content.strip().split("\n"):
            if not line:
                continue
            parts = line.split("  ", 1)
            if len(parts) != 2:
                errors.append(f"Malformed checksum line: {line}")
                continue
            
            expected_hash, path = parts
            
            if path == "checksums.sha256":
                continue  # Skip self-reference
            
            if path not in zf.namelist():
                errors.append(f"Missing file: {path}")
                continue
            
            actual_hash = compute_sha256(zf.read(path))
            if actual_hash != expected_hash:
                errors.append(f"Checksum mismatch for {path}")
    
    return len(errors) == 0, errors


def get_level_json(
    stella_path: Union[str, Path],
    level_id: str = "0",
) -> LevelJson:
    """
    Read and parse a level.json from a .stella file.
    
    Args:
        stella_path: Path to .stella file
        level_id: Level ID to read
    
    Returns:
        LevelJson instance
    """
    manifest, zf = unpack_stella(stella_path)
    
    try:
        level_ref = next((l for l in manifest.levels if l.id == level_id), None)
        if not level_ref:
            raise ValueError(f"Level {level_id} not found in manifest")
        
        level_bytes = zf.read(level_ref.path)
        return LevelJson.from_json(level_bytes.decode("utf-8"))
    finally:
        zf.close()


def list_stella_contents(stella_path: Union[str, Path]) -> List[str]:
    """
    List all files in a .stella archive.
    
    Args:
        stella_path: Path to .stella file
    
    Returns:
        List of file paths within the archive
    """
    with zipfile.ZipFile(stella_path, "r") as zf:
        return zf.namelist()


def validate_stella(stella_path: Union[str, Path]) -> Tuple[bool, List[str]]:
    """
    Validate a .stella file structure and contents.
    
    Checks:
    - Valid ZIP archive
    - manifest.json exists and is valid JSON
    - Each level has level.json, render.glb, collision.rlevox
    - If checksums.sha256 exists, verify file hashes
    
    Args:
        stella_path: Path to .stella file
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    
    Example:
        >>> is_valid, errors = validate_stella("world.stella")
        >>> if not is_valid:
        ...     print(f"Validation failed: {errors}")
    """
    errors = []
    stella_path = Path(stella_path)
    
    # Check file exists
    if not stella_path.exists():
        return False, [f"File not found: {stella_path}"]
    
    # Check valid ZIP
    try:
        zf = zipfile.ZipFile(stella_path, "r")
    except zipfile.BadZipFile:
        return False, ["Not a valid ZIP file"]
    
    try:
        # Check manifest exists
        if "manifest.json" not in zf.namelist():
            errors.append("Missing required file: manifest.json")
        else:
            try:
                manifest_bytes = zf.read("manifest.json")
                manifest_data = json.loads(manifest_bytes.decode("utf-8"))
                
                # Check manifest has levels
                if "levels" not in manifest_data:
                    errors.append("manifest.json missing 'levels' field")
                elif not manifest_data["levels"]:
                    errors.append("manifest.json has empty 'levels' array")
                else:
                    # Check each level has required files
                    for level in manifest_data["levels"]:
                        level_id = level.get("id", "unknown")
                        level_dir = f"levels/{level_id}/"
                        
                        required_files = [
                            f"{level_dir}level.json",
                            f"{level_dir}render.glb",
                            f"{level_dir}collision.rlevox",
                        ]
                        
                        for req_file in required_files:
                            if req_file not in zf.namelist():
                                errors.append(f"Missing required file: {req_file}")
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON in manifest.json: {e}")
        
        # Verify checksums if present
        if "checksums.sha256" in zf.namelist():
            checksum_valid, checksum_errors = verify_stella_checksums(stella_path)
            if not checksum_valid:
                errors.extend(checksum_errors)
    
    finally:
        zf.close()
    
    return len(errors) == 0, errors
