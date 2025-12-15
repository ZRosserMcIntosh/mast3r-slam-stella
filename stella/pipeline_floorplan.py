"""
Floorplan to .stella pipeline.

Converts a 2D floorplan image into a navigable 3D world.
"""

import os
import json
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import trimesh
    HAS_TRIMESH = True
except ImportError:
    HAS_TRIMESH = False

from stella.manifest import (
    Manifest, Level, World, Generator, Axis,
    LevelJson, Spawn, RenderAsset, CollisionAsset, PlayerCollision, NavigationAsset,
    make_manifest, make_level_json,
)
from stella.package import pack_stella
from stella.vox_rle import write_rlevox
from stella.geometry import extrude_2d_to_walls, compute_spawn_position


def build_floorplan(
    input_image: str,
    output_stella: str,
    wall_height: float = 2.7,
    voxel_size: float = 0.1,
    pixels_per_meter: float = 50.0,
    title: str = "Floorplan World",
    invert: bool = False,
    threshold: int = 128,
) -> str:
    """
    Build a .stella file from a floorplan image.
    
    Args:
        input_image: Path to input floorplan image (PNG/JPG)
        output_stella: Path for output .stella file
        wall_height: Height of walls in meters
        voxel_size: Size of each voxel in meters
        pixels_per_meter: Scale factor for image
        title: World title
        invert: If True, dark pixels are empty (not walls)
        threshold: Grayscale threshold for wall detection
    
    Returns:
        Path to created .stella file
    
    Example:
        >>> build_floorplan("plan.png", "out.stella", wall_height=2.7, voxel_size=0.1)
    """
    if not HAS_CV2:
        raise ImportError("opencv-python is required for floorplan pipeline. Install with: pip install opencv-python")
    
    if not HAS_TRIMESH:
        raise ImportError("trimesh is required for floorplan pipeline. Install with: pip install trimesh")
    
    input_path = Path(input_image)
    output_path = Path(output_stella)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_image}")
    
    # Load and process image
    print(f"Loading floorplan: {input_image}")
    image = cv2.imread(str(input_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Could not read image: {input_image}")
    
    # Threshold to binary
    if invert:
        _, binary = cv2.threshold(image, threshold, 255, cv2.THRESH_BINARY)
    else:
        _, binary = cv2.threshold(image, threshold, 255, cv2.THRESH_BINARY_INV)
    
    # Morphological cleanup
    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    
    # Convert to occupancy grid (True = wall)
    occupancy_2d = binary > 0
    
    # Scale based on pixels_per_meter
    # Each pixel in the image = 1/pixels_per_meter meters
    # Each voxel = voxel_size meters
    # So scale_factor = (1/pixels_per_meter) / voxel_size = 1 / (pixels_per_meter * voxel_size)
    scale_factor = 1.0 / (pixels_per_meter * voxel_size)
    
    if scale_factor != 1.0:
        new_height = int(occupancy_2d.shape[0] * scale_factor)
        new_width = int(occupancy_2d.shape[1] * scale_factor)
        occupancy_2d = cv2.resize(
            occupancy_2d.astype(np.uint8) * 255,
            (new_width, new_height),
            interpolation=cv2.INTER_NEAREST
        ) > 127
    
    print(f"Occupancy grid size: {occupancy_2d.shape}")
    
    # Extrude to 3D
    dim_y = int(np.ceil(wall_height / voxel_size))
    grid_3d = extrude_2d_to_walls(occupancy_2d, 0, wall_height, voxel_size)
    
    # Note: grid_3d is [x, y, z] where x corresponds to image rows, z to columns
    # We need to transpose to match our coordinate system
    # Image: rows=Y_image (top-down), cols=X_image (left-right)
    # World: X=right, Y=up, Z=forward
    
    dim_x, dim_y, dim_z = grid_3d.shape
    origin = (0.0, 0.0, 0.0)
    
    print(f"3D grid dimensions: {grid_3d.shape}")
    print(f"World size: {dim_x * voxel_size:.1f}m x {dim_y * voxel_size:.1f}m x {dim_z * voxel_size:.1f}m")
    
    # Find spawn position
    spawn_pos = compute_spawn_position(grid_3d, voxel_size, origin)
    if spawn_pos is None:
        # Default to center if no valid position found
        spawn_pos = [dim_x * voxel_size / 2, 1.7, dim_z * voxel_size / 2]
        print("Warning: Could not find valid spawn position, using center")
    else:
        print(f"Spawn position: {spawn_pos}")
    
    # Create mesh for rendering
    print("Creating render mesh...")
    mesh = create_wall_mesh_from_2d(occupancy_2d, wall_height, voxel_size)
    
    # Use temp directory for intermediate files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Write collision data
        collision_path = tmpdir / "collision.rlevox"
        write_rlevox(collision_path, grid_3d, voxel_size, origin)
        print(f"Collision data written: {grid_3d.sum()} solid voxels")
        
        # Write render mesh
        render_path = tmpdir / "render.glb"
        mesh.export(str(render_path))
        print(f"Render mesh written: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
        
        # Create level.json
        level_json = make_level_json(
            name="Floor 0",
            spawn_position=spawn_pos,
            player_height=1.7,
        )
        
        # Create manifest
        manifest = make_manifest(
            title=title,
            tags=["floorplan", "generated"],
        )
        
        # Read file bytes
        file_map = {
            "levels/0/level.json": level_json.to_json().encode("utf-8"),
            "levels/0/render.glb": render_path.read_bytes(),
            "levels/0/collision.rlevox": collision_path.read_bytes(),
        }
        
        # Pack stella file
        output_path = pack_stella(output_stella, manifest, file_map)
        print(f"Created: {output_path}")
    
    return str(output_path)


def create_wall_mesh_from_2d(
    occupancy_2d: np.ndarray,
    wall_height: float,
    voxel_size: float,
) -> "trimesh.Trimesh":
    """
    Create a mesh from 2D occupancy grid by extruding walls.
    
    Args:
        occupancy_2d: 2D boolean array (True = wall)
        wall_height: Height of walls in meters
        voxel_size: Size of each voxel/pixel in meters
    
    Returns:
        trimesh.Trimesh mesh
    """
    vertices = []
    faces = []
    vertex_offset = 0
    
    dim_x, dim_z = occupancy_2d.shape
    
    # For each wall pixel, create a box
    wall_indices = np.argwhere(occupancy_2d)
    
    for idx in wall_indices:
        x, z = idx
        
        # Box corners
        x0 = x * voxel_size
        x1 = (x + 1) * voxel_size
        z0 = z * voxel_size
        z1 = (z + 1) * voxel_size
        y0 = 0
        y1 = wall_height
        
        # 8 vertices of the box
        box_verts = [
            [x0, y0, z0],  # 0
            [x1, y0, z0],  # 1
            [x1, y1, z0],  # 2
            [x0, y1, z0],  # 3
            [x0, y0, z1],  # 4
            [x1, y0, z1],  # 5
            [x1, y1, z1],  # 6
            [x0, y1, z1],  # 7
        ]
        
        # 12 triangles (2 per face)
        box_faces = [
            # Front
            [0, 2, 1], [0, 3, 2],
            # Back
            [4, 5, 6], [4, 6, 7],
            # Left
            [0, 4, 7], [0, 7, 3],
            # Right
            [1, 2, 6], [1, 6, 5],
            # Bottom
            [0, 1, 5], [0, 5, 4],
            # Top
            [3, 6, 2], [3, 7, 6],
        ]
        
        vertices.extend(box_verts)
        faces.extend([[f[0] + vertex_offset, f[1] + vertex_offset, f[2] + vertex_offset] for f in box_faces])
        vertex_offset += 8
    
    # Add floor plane
    floor_verts = [
        [0, 0, 0],
        [dim_x * voxel_size, 0, 0],
        [dim_x * voxel_size, 0, dim_z * voxel_size],
        [0, 0, dim_z * voxel_size],
    ]
    floor_faces = [
        [vertex_offset + 0, vertex_offset + 2, vertex_offset + 1],
        [vertex_offset + 0, vertex_offset + 3, vertex_offset + 2],
    ]
    vertices.extend(floor_verts)
    faces.extend(floor_faces)
    
    vertices = np.array(vertices, dtype=np.float32)
    faces = np.array(faces, dtype=np.int32)
    
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    
    # Merge duplicate vertices
    mesh.merge_vertices()
    
    return mesh


def preview_floorplan(
    input_image: str,
    threshold: int = 128,
    invert: bool = False,
) -> np.ndarray:
    """
    Preview the wall detection on a floorplan image.
    
    Args:
        input_image: Path to floorplan image
        threshold: Grayscale threshold
        invert: Invert wall detection
    
    Returns:
        Preview image with walls highlighted
    """
    if not HAS_CV2:
        raise ImportError("opencv-python is required")
    
    image = cv2.imread(input_image, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Could not read image: {input_image}")
    
    if invert:
        _, binary = cv2.threshold(image, threshold, 255, cv2.THRESH_BINARY)
    else:
        _, binary = cv2.threshold(image, threshold, 255, cv2.THRESH_BINARY_INV)
    
    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    
    # Create preview
    preview = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    preview[binary > 0] = [0, 0, 255]  # Red for walls
    
    return preview
