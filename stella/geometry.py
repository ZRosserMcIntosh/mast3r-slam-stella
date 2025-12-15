"""
Geometry utilities for .stella world generation.

Includes floor plane fitting, mesh generation, and coordinate transforms.
"""

import numpy as np
from typing import Tuple, Optional, List


def fit_floor_plane_ransac(
    points: np.ndarray,
    n_iterations: int = 1000,
    distance_threshold: float = 0.05,
    min_inlier_ratio: float = 0.1,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Fit a floor plane using RANSAC.
    
    Assumes floor is roughly horizontal (largest horizontal plane).
    
    Args:
        points: Nx3 array of world coordinates
        n_iterations: RANSAC iterations
        distance_threshold: Max distance from plane for inlier (meters)
        min_inlier_ratio: Minimum fraction of points as inliers
    
    Returns:
        Tuple of:
        - normal: Unit normal vector (pointing up)
        - point: A point on the plane
        - inliers: Boolean mask of inlier points
    
    Raises:
        ValueError: If no plane found with enough inliers
    """
    points = np.asarray(points)
    n_points = len(points)
    
    if n_points < 3:
        raise ValueError("Need at least 3 points to fit a plane")
    
    best_inliers = None
    best_normal = None
    best_point = None
    best_n_inliers = 0
    
    for _ in range(n_iterations):
        # Sample 3 random points
        idx = np.random.choice(n_points, 3, replace=False)
        p1, p2, p3 = points[idx]
        
        # Compute plane normal
        v1 = p2 - p1
        v2 = p3 - p1
        normal = np.cross(v1, v2)
        norm = np.linalg.norm(normal)
        
        if norm < 1e-10:
            continue  # Degenerate (collinear points)
        
        normal = normal / norm
        
        # Ensure normal points up (positive Y)
        if normal[1] < 0:
            normal = -normal
        
        # Skip if plane is too tilted (not floor-like)
        # Floor should be mostly horizontal (normal ~= [0, 1, 0])
        if abs(normal[1]) < 0.7:
            continue
        
        # Compute distances to plane
        d = -np.dot(normal, p1)
        distances = np.abs(np.dot(points, normal) + d)
        
        # Count inliers
        inliers = distances < distance_threshold
        n_inliers = np.sum(inliers)
        
        if n_inliers > best_n_inliers:
            best_n_inliers = n_inliers
            best_inliers = inliers
            best_normal = normal
            best_point = p1
    
    if best_n_inliers < min_inlier_ratio * n_points:
        raise ValueError(f"Could not find floor plane with enough inliers ({best_n_inliers}/{n_points})")
    
    return best_normal, best_point, best_inliers


def compute_floor_height(
    points: np.ndarray,
    floor_normal: np.ndarray,
    floor_point: np.ndarray,
) -> float:
    """
    Compute the floor height (Y coordinate) given a floor plane.
    
    Args:
        points: Nx3 array of points
        floor_normal: Unit normal of floor plane
        floor_point: A point on the floor plane
    
    Returns:
        Floor height in world coordinates
    """
    # Project floor_point onto Y axis using the plane equation
    # Plane: normal · (p - floor_point) = 0
    # For a horizontal floor, this is approximately floor_point[1]
    return float(floor_point[1])


def align_to_gravity(
    points: np.ndarray,
    floor_normal: np.ndarray,
    floor_point: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Rotate points so floor normal aligns with +Y axis.
    
    Args:
        points: Nx3 array of points
        floor_normal: Floor plane normal
        floor_point: A point on the floor
    
    Returns:
        Tuple of:
        - aligned_points: Rotated points
        - rotation_matrix: 3x3 rotation matrix applied
    """
    target = np.array([0.0, 1.0, 0.0])
    
    # Compute rotation axis and angle
    axis = np.cross(floor_normal, target)
    axis_norm = np.linalg.norm(axis)
    
    if axis_norm < 1e-10:
        # Already aligned
        return points.copy(), np.eye(3)
    
    axis = axis / axis_norm
    angle = np.arccos(np.clip(np.dot(floor_normal, target), -1.0, 1.0))
    
    # Rodrigues' rotation formula
    R = rotation_matrix_from_axis_angle(axis, angle)
    
    # Rotate points
    aligned = (R @ points.T).T
    
    return aligned, R


def rotation_matrix_from_axis_angle(axis: np.ndarray, angle: float) -> np.ndarray:
    """
    Create a rotation matrix from axis-angle representation.
    
    Args:
        axis: Unit rotation axis
        angle: Rotation angle in radians
    
    Returns:
        3x3 rotation matrix
    """
    c = np.cos(angle)
    s = np.sin(angle)
    t = 1 - c
    x, y, z = axis
    
    return np.array([
        [t*x*x + c,   t*x*y - z*s, t*x*z + y*s],
        [t*x*y + z*s, t*y*y + c,   t*y*z - x*s],
        [t*x*z - y*s, t*y*z + x*s, t*z*z + c  ],
    ])


def extrude_2d_to_walls(
    occupancy_2d: np.ndarray,
    floor_height: float,
    wall_height: float,
    voxel_size: float,
) -> np.ndarray:
    """
    Extrude a 2D occupancy grid into 3D walls.
    
    Args:
        occupancy_2d: 2D boolean array (True = wall)
        floor_height: Height of floor in voxels
        wall_height: Height of walls in meters
        voxel_size: Size of each voxel in meters
    
    Returns:
        3D boolean array [x, y, z] where y is up
    """
    dim_x, dim_z = occupancy_2d.shape
    dim_y = int(np.ceil(wall_height / voxel_size))
    
    grid_3d = np.zeros((dim_x, dim_y, dim_z), dtype=bool)
    
    # Extrude walls vertically
    for y in range(dim_y):
        grid_3d[:, y, :] = occupancy_2d
    
    return grid_3d


def create_floor_ceiling_grid(
    bounds_xz: Tuple[int, int],
    floor_thickness: int = 1,
    ceiling_height: int = 27,  # e.g., 2.7m at 0.1m voxels
    ceiling_thickness: int = 1,
) -> np.ndarray:
    """
    Create a voxel grid with floor and ceiling.
    
    Args:
        bounds_xz: (dim_x, dim_z) dimensions
        floor_thickness: Floor thickness in voxels
        ceiling_height: Height to ceiling in voxels
        ceiling_thickness: Ceiling thickness in voxels
    
    Returns:
        3D boolean grid
    """
    dim_x, dim_z = bounds_xz
    dim_y = ceiling_height + ceiling_thickness
    
    grid = np.zeros((dim_x, dim_y, dim_z), dtype=bool)
    
    # Floor
    grid[:, :floor_thickness, :] = True
    
    # Ceiling
    grid[:, ceiling_height:ceiling_height + ceiling_thickness, :] = True
    
    return grid


def create_box_mesh(
    min_corner: np.ndarray,
    max_corner: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Create a box mesh from min/max corners.
    
    Args:
        min_corner: [x, y, z] minimum corner
        max_corner: [x, y, z] maximum corner
    
    Returns:
        Tuple of (vertices, faces)
    """
    x0, y0, z0 = min_corner
    x1, y1, z1 = max_corner
    
    vertices = np.array([
        [x0, y0, z0],  # 0
        [x1, y0, z0],  # 1
        [x1, y1, z0],  # 2
        [x0, y1, z0],  # 3
        [x0, y0, z1],  # 4
        [x1, y0, z1],  # 5
        [x1, y1, z1],  # 6
        [x0, y1, z1],  # 7
    ])
    
    # Each face as two triangles
    faces = np.array([
        # Front (z=0)
        [0, 1, 2], [0, 2, 3],
        # Back (z=1)
        [4, 6, 5], [4, 7, 6],
        # Left (x=0)
        [0, 3, 7], [0, 7, 4],
        # Right (x=1)
        [1, 5, 6], [1, 6, 2],
        # Bottom (y=0)
        [0, 4, 5], [0, 5, 1],
        # Top (y=1)
        [3, 2, 6], [3, 6, 7],
    ])
    
    return vertices, faces


def voxel_grid_to_mesh(
    grid: np.ndarray,
    voxel_size: float,
    origin: Tuple[float, float, float],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert a voxel grid to a triangle mesh (naive approach).
    
    Creates one box per solid voxel. Not optimized - use for small grids.
    
    Args:
        grid: 3D boolean array [x, y, z]
        voxel_size: Size of each voxel in meters
        origin: World origin of voxel [0,0,0]
    
    Returns:
        Tuple of (vertices, faces) for triangle mesh
    """
    all_vertices = []
    all_faces = []
    vertex_offset = 0
    
    origin_arr = np.array(origin)
    solid_indices = np.argwhere(grid)
    
    for idx in solid_indices:
        min_corner = origin_arr + idx * voxel_size
        max_corner = min_corner + voxel_size
        
        box_verts, box_faces = create_box_mesh(min_corner, max_corner)
        
        all_vertices.append(box_verts)
        all_faces.append(box_faces + vertex_offset)
        vertex_offset += len(box_verts)
    
    if len(all_vertices) == 0:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=int)
    
    vertices = np.vstack(all_vertices)
    faces = np.vstack(all_faces)
    
    return vertices, faces


def greedy_mesh_voxels(
    grid: np.ndarray,
    voxel_size: float,
    origin: Tuple[float, float, float],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert voxel grid to mesh using greedy meshing (more efficient).
    
    Groups adjacent voxels into larger quads to reduce face count.
    
    Args:
        grid: 3D boolean array [x, y, z]
        voxel_size: Size of each voxel
        origin: World origin
    
    Returns:
        Tuple of (vertices, faces)
    """
    # For now, fall back to naive approach
    # TODO: Implement proper greedy meshing
    return voxel_grid_to_mesh(grid, voxel_size, origin)


def compute_spawn_position(
    grid: np.ndarray,
    voxel_size: float,
    origin: Tuple[float, float, float],
    player_height: float = 1.7,
    player_radius: float = 0.3,
) -> Optional[List[float]]:
    """
    Find a valid spawn position in the world.
    
    Searches for an empty space that can fit the player.
    
    Args:
        grid: 3D boolean voxel grid
        voxel_size: Size of each voxel
        origin: World origin
        player_height: Player height in meters
        player_radius: Player radius in meters
    
    Returns:
        [x, y, z] spawn position or None if no valid position found
    """
    dim_x, dim_y, dim_z = grid.shape
    origin_arr = np.array(origin)
    
    player_height_voxels = int(np.ceil(player_height / voxel_size))
    player_radius_voxels = int(np.ceil(player_radius / voxel_size))
    
    # Search for empty column
    for x in range(player_radius_voxels, dim_x - player_radius_voxels):
        for z in range(player_radius_voxels, dim_z - player_radius_voxels):
            # Find lowest empty y with enough headroom
            for y in range(dim_y - player_height_voxels):
                # Check if space is clear
                region = grid[
                    x - player_radius_voxels:x + player_radius_voxels + 1,
                    y:y + player_height_voxels,
                    z - player_radius_voxels:z + player_radius_voxels + 1
                ]
                
                if not region.any():
                    # Found clear space, check if standing on ground
                    if y == 0 or grid[x, y - 1, z]:
                        world_pos = origin_arr + np.array([x + 0.5, y, z + 0.5]) * voxel_size
                        return world_pos.tolist()
    
    return None


def calculate_distance(point_a: np.ndarray, point_b: np.ndarray) -> float:
    """Calculate Euclidean distance between two points."""
    return float(np.linalg.norm(np.array(point_a) - np.array(point_b)))


def calculate_centroid(points: np.ndarray) -> np.ndarray:
    """Calculate the centroid of a set of points."""
    return np.mean(points, axis=0)


def is_point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """
    Determine if a point is inside a polygon using ray-casting.
    
    Args:
        point: (x, y) point to test
        polygon: List of (x, y) vertices
    
    Returns:
        True if point is inside polygon
    """
    x, y = point
    inside = False
    n = len(polygon)
    
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside


def transform_point(point: np.ndarray, transformation_matrix: np.ndarray) -> np.ndarray:
    """Transform a point using a 4x4 transformation matrix."""
    point_homogeneous = np.append(point, 1)
    transformed_point = transformation_matrix @ point_homogeneous
    return transformed_point[:3]
