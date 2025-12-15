"""
RLEVOX (Run-Length Encoded Voxel) format for collision data.

File format specification:
- Magic: "STVX" (4 bytes)
- Version: uint16 (2 bytes) 
- Header size: uint16 (2 bytes)
- Dimensions: dim_x, dim_y, dim_z (3 x uint32 = 12 bytes)
- Voxel size: float32 (4 bytes)
- Origin: origin_x, origin_y, origin_z (3 x float32 = 12 bytes)
- Encoding: "RLE1" (4 bytes)
- Reserved: uint32 (4 bytes)
- Padding to 64 bytes
- Payload: RLE runs for each (z, y) row

Coordinate convention:
- Grid indices are [x, y, z] 
- World position = origin + (index * voxel_size)
- Y-up, right-handed coordinate system

RLE format:
- Each (z, y) row is encoded as runs along X
- Run: (length: uint16, value: uint8, flags: uint8)
- Value: 0 = empty, 1 = solid
- Sum of run lengths must equal dim_x
"""

import struct
import numpy as np
from pathlib import Path
from typing import Union, Tuple, Optional

# Constants
MAGIC = b"STVX"
VERSION = 1
HEADER_SIZE = 64
ENCODING = b"RLE1"


def write_rlevox(
    path: Union[str, Path],
    grid: np.ndarray,
    voxel_size: float,
    origin: Tuple[float, float, float],
) -> None:
    """
    Write a voxel grid to RLEVOX format.
    
    Args:
        path: Output file path
        grid: 3D boolean numpy array with shape [dim_x, dim_y, dim_z]
              True = solid, False = empty
        voxel_size: Size of each voxel in meters
        origin: World-space origin (x, y, z) of voxel [0,0,0]
    
    Example:
        >>> grid = np.zeros((100, 50, 100), dtype=bool)
        >>> grid[10:90, 0:3, 10:90] = True  # Floor
        >>> grid[10:12, 0:30, 10:90] = True  # Wall
        >>> write_rlevox("collision.rlevox", grid, 0.1, (0.0, 0.0, 0.0))
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    grid = np.asarray(grid, dtype=bool)
    
    if grid.ndim != 3:
        raise ValueError(f"Grid must be 3D, got shape {grid.shape}")
    
    dim_x, dim_y, dim_z = grid.shape
    origin_x, origin_y, origin_z = origin
    
    with open(path, "wb") as f:
        # Write header
        f.write(MAGIC)  # 4 bytes
        f.write(struct.pack("<H", VERSION))  # 2 bytes
        f.write(struct.pack("<H", HEADER_SIZE))  # 2 bytes
        
        f.write(struct.pack("<I", dim_x))  # 4 bytes
        f.write(struct.pack("<I", dim_y))  # 4 bytes
        f.write(struct.pack("<I", dim_z))  # 4 bytes
        
        f.write(struct.pack("<f", voxel_size))  # 4 bytes
        
        f.write(struct.pack("<f", origin_x))  # 4 bytes
        f.write(struct.pack("<f", origin_y))  # 4 bytes
        f.write(struct.pack("<f", origin_z))  # 4 bytes
        
        f.write(ENCODING)  # 4 bytes
        f.write(struct.pack("<I", 0))  # 4 bytes reserved
        
        # Pad to header size (64 bytes total)
        # 4+2+2+4+4+4+4+4+4+4+4+4 = 44 bytes written, need 20 more
        current_pos = f.tell()
        if current_pos < HEADER_SIZE:
            f.write(b"\x00" * (HEADER_SIZE - current_pos))
        
        # Write RLE payload
        # Iterate z, then y, encoding runs along x
        for z in range(dim_z):
            for y in range(dim_y):
                row = grid[:, y, z]
                runs = _encode_rle_row(row)
                for run_length, value in runs:
                    # Split long runs (run_length max is 65535)
                    remaining = run_length
                    while remaining > 0:
                        chunk = min(remaining, 65535)
                        f.write(struct.pack("<H", chunk))  # run_length
                        f.write(struct.pack("<B", value))  # value (0 or 1)
                        f.write(struct.pack("<B", 0))  # flags (reserved)
                        remaining -= chunk


def read_rlevox(
    path: Union[str, Path],
) -> Tuple[np.ndarray, float, Tuple[float, float, float]]:
    """
    Read a RLEVOX file and return the voxel grid.
    
    Args:
        path: Path to .rlevox file
    
    Returns:
        Tuple of:
        - grid: 3D boolean numpy array [dim_x, dim_y, dim_z]
        - voxel_size: Size of each voxel in meters  
        - origin: World-space origin (x, y, z) of voxel [0,0,0]
    
    Raises:
        ValueError: If file format is invalid
    """
    path = Path(path)
    
    with open(path, "rb") as f:
        # Read and verify magic
        magic = f.read(4)
        if magic != MAGIC:
            raise ValueError(f"Invalid magic: {magic}, expected {MAGIC}")
        
        version = struct.unpack("<H", f.read(2))[0]
        if version != VERSION:
            raise ValueError(f"Unsupported version: {version}")
        
        header_size = struct.unpack("<H", f.read(2))[0]
        
        dim_x = struct.unpack("<I", f.read(4))[0]
        dim_y = struct.unpack("<I", f.read(4))[0]
        dim_z = struct.unpack("<I", f.read(4))[0]
        
        voxel_size = struct.unpack("<f", f.read(4))[0]
        
        origin_x = struct.unpack("<f", f.read(4))[0]
        origin_y = struct.unpack("<f", f.read(4))[0]
        origin_z = struct.unpack("<f", f.read(4))[0]
        
        encoding = f.read(4)
        if encoding != ENCODING:
            raise ValueError(f"Unsupported encoding: {encoding}")
        
        _reserved = struct.unpack("<I", f.read(4))[0]
        
        # Skip to payload
        f.seek(header_size)
        
        # Read RLE payload
        grid = np.zeros((dim_x, dim_y, dim_z), dtype=bool)
        
        for z in range(dim_z):
            for y in range(dim_y):
                x = 0
                while x < dim_x:
                    run_data = f.read(4)
                    if len(run_data) < 4:
                        raise ValueError(f"Unexpected EOF at z={z}, y={y}, x={x}")
                    
                    run_length = struct.unpack("<H", run_data[0:2])[0]
                    value = struct.unpack("<B", run_data[2:3])[0]
                    _flags = struct.unpack("<B", run_data[3:4])[0]
                    
                    if run_length == 0:
                        raise ValueError(f"Invalid run_length=0 at z={z}, y={y}")
                    
                    end_x = min(x + run_length, dim_x)
                    if value == 1:
                        grid[x:end_x, y, z] = True
                    x = end_x
                
                if x != dim_x:
                    raise ValueError(f"Row length mismatch at z={z}, y={y}: got {x}, expected {dim_x}")
        
        return grid, voxel_size, (origin_x, origin_y, origin_z)


def _encode_rle_row(row: np.ndarray) -> list:
    """
    Encode a 1D boolean array as RLE runs.
    
    Args:
        row: 1D boolean array
    
    Returns:
        List of (run_length, value) tuples
    """
    if len(row) == 0:
        return []
    
    runs = []
    current_value = int(row[0])
    run_length = 1
    
    for i in range(1, len(row)):
        value = int(row[i])
        if value == current_value:
            run_length += 1
        else:
            runs.append((run_length, current_value))
            current_value = value
            run_length = 1
    
    runs.append((run_length, current_value))
    return runs


def grid_to_world(
    indices: np.ndarray,
    voxel_size: float,
    origin: Tuple[float, float, float],
) -> np.ndarray:
    """
    Convert voxel indices to world coordinates (center of voxel).
    
    Args:
        indices: Nx3 array of [x, y, z] voxel indices
        voxel_size: Size of each voxel
        origin: World origin of voxel [0,0,0]
    
    Returns:
        Nx3 array of world coordinates (center of each voxel)
    """
    origin_arr = np.array(origin)
    return origin_arr + (indices + 0.5) * voxel_size


def world_to_grid(
    positions: np.ndarray,
    voxel_size: float,
    origin: Tuple[float, float, float],
) -> np.ndarray:
    """
    Convert world coordinates to voxel indices.
    
    Args:
        positions: Nx3 array of world coordinates
        voxel_size: Size of each voxel
        origin: World origin of voxel [0,0,0]
    
    Returns:
        Nx3 array of voxel indices (integers)
    """
    origin_arr = np.array(origin)
    return np.floor((positions - origin_arr) / voxel_size).astype(int)


def check_collision_point(
    grid: np.ndarray,
    position: np.ndarray,
    voxel_size: float,
    origin: Tuple[float, float, float],
) -> bool:
    """
    Check if a single point is inside a solid voxel.
    
    Args:
        grid: 3D boolean voxel grid [x, y, z]
        position: World position as [x, y, z]
        voxel_size: Size of each voxel
        origin: World origin
    
    Returns:
        True if point is inside solid voxel
    """
    dim_x, dim_y, dim_z = grid.shape
    idx = world_to_grid(np.array([position]), voxel_size, origin)[0]
    
    if (idx[0] < 0 or idx[0] >= dim_x or
        idx[1] < 0 or idx[1] >= dim_y or
        idx[2] < 0 or idx[2] >= dim_z):
        return False
    
    return grid[idx[0], idx[1], idx[2]]


def check_collision_capsule(
    grid: np.ndarray,
    position: np.ndarray,
    radius: float,
    height: float,
    voxel_size: float,
    origin: Tuple[float, float, float],
) -> bool:
    """
    Check if a player capsule collides with the voxel grid.
    
    Uses AABB approximation for simplicity (capsule bounding box).
    
    Args:
        grid: 3D boolean voxel grid [x, y, z]
        position: Player position (feet) as [x, y, z]
        radius: Player capsule radius
        height: Player capsule height
        voxel_size: Size of each voxel
        origin: World origin
    
    Returns:
        True if collision detected
    """
    dim_x, dim_y, dim_z = grid.shape
    origin_arr = np.array(origin)
    
    # Get bounding box of player capsule in voxel space
    min_pos = position - np.array([radius, 0, radius])
    max_pos = position + np.array([radius, height, radius])
    
    min_idx = np.floor((min_pos - origin_arr) / voxel_size).astype(int)
    max_idx = np.ceil((max_pos - origin_arr) / voxel_size).astype(int)
    
    # Clamp to grid bounds
    min_idx = np.maximum(min_idx, 0)
    max_idx = np.minimum(max_idx, [dim_x, dim_y, dim_z])
    
    # Check all voxels in bounding box
    for x in range(min_idx[0], max_idx[0]):
        for y in range(min_idx[1], max_idx[1]):
            for z in range(min_idx[2], max_idx[2]):
                if grid[x, y, z]:
                    return True
    
    return False


def voxelize_points(
    points: np.ndarray,
    voxel_size: float,
    padding: int = 1,
) -> Tuple[np.ndarray, Tuple[float, float, float]]:
    """
    Convert a point cloud to a voxel occupancy grid.
    
    Args:
        points: Nx3 array of world coordinates
        voxel_size: Size of each voxel in meters
        padding: Extra voxels around bounds
    
    Returns:
        Tuple of:
        - grid: 3D boolean array [dim_x, dim_y, dim_z]
        - origin: World origin of voxel [0,0,0]
    """
    if len(points) == 0:
        return np.zeros((1, 1, 1), dtype=bool), (0.0, 0.0, 0.0)
    
    points = np.asarray(points)
    
    # Compute bounds
    min_pt = points.min(axis=0) - padding * voxel_size
    max_pt = points.max(axis=0) + padding * voxel_size
    
    # Compute grid dimensions
    dims = np.ceil((max_pt - min_pt) / voxel_size).astype(int)
    dims = np.maximum(dims, 1)
    
    # Create empty grid
    grid = np.zeros(dims, dtype=bool)
    
    # Convert points to indices and mark occupied
    indices = np.floor((points - min_pt) / voxel_size).astype(int)
    indices = np.clip(indices, 0, dims - 1)
    
    grid[indices[:, 0], indices[:, 1], indices[:, 2]] = True
    
    origin = tuple(min_pt.tolist())
    return grid, origin


def dilate_grid(grid: np.ndarray, iterations: int = 1) -> np.ndarray:
    """
    Dilate a voxel grid (expand solid regions).
    
    Args:
        grid: 3D boolean array
        iterations: Number of dilation iterations
    
    Returns:
        Dilated grid
    """
    from scipy import ndimage
    
    struct = ndimage.generate_binary_structure(3, 1)  # 6-connectivity
    return ndimage.binary_dilation(grid, structure=struct, iterations=iterations)


def erode_grid(grid: np.ndarray, iterations: int = 1) -> np.ndarray:
    """
    Erode a voxel grid (shrink solid regions).
    
    Args:
        grid: 3D boolean array
        iterations: Number of erosion iterations
    
    Returns:
        Eroded grid
    """
    from scipy import ndimage
    
    struct = ndimage.generate_binary_structure(3, 1)  # 6-connectivity
    return ndimage.binary_erosion(grid, structure=struct, iterations=iterations)


def fill_holes(grid: np.ndarray) -> np.ndarray:
    """
    Fill internal holes in a voxel grid.
    
    Args:
        grid: 3D boolean array
    
    Returns:
        Grid with holes filled
    """
    from scipy import ndimage
    
    return ndimage.binary_fill_holes(grid)


def remove_small_components(
    grid: np.ndarray,
    min_size: int = 10,
) -> np.ndarray:
    """
    Remove small disconnected components from voxel grid.
    
    Args:
        grid: 3D boolean array
        min_size: Minimum component size to keep
    
    Returns:
        Cleaned grid
    """
    from scipy import ndimage
    
    labeled, num_features = ndimage.label(grid)
    component_sizes = ndimage.sum(grid, labeled, range(1, num_features + 1))
    
    # Create mask of large enough components
    large_components = np.zeros_like(grid)
    for i, size in enumerate(component_sizes, 1):
        if size >= min_size:
            large_components |= (labeled == i)
    
    return large_components


def get_grid_stats(grid: np.ndarray, voxel_size: float) -> dict:
    """
    Get statistics about a voxel grid.
    
    Args:
        grid: 3D boolean array
        voxel_size: Size of each voxel in meters
    
    Returns:
        Dict with statistics
    """
    dim_x, dim_y, dim_z = grid.shape
    total_voxels = dim_x * dim_y * dim_z
    solid_voxels = grid.sum()
    
    return {
        "dimensions": (dim_x, dim_y, dim_z),
        "voxel_size_m": voxel_size,
        "total_voxels": total_voxels,
        "solid_voxels": int(solid_voxels),
        "empty_voxels": total_voxels - int(solid_voxels),
        "fill_ratio": float(solid_voxels / total_voxels) if total_voxels > 0 else 0,
        "world_size_m": (dim_x * voxel_size, dim_y * voxel_size, dim_z * voxel_size),
    }
