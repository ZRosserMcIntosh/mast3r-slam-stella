"""
Video to .stella pipeline using MASt3R-SLAM.

Converts video input into a navigable 3D world by running SLAM reconstruction.
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List
import numpy as np

try:
    import trimesh
    HAS_TRIMESH = True
except ImportError:
    HAS_TRIMESH = False

from stella.manifest import make_manifest, make_level_json
from stella.package import pack_stella
from stella.vox_rle import write_rlevox, voxelize_points
from stella.geometry import (
    fit_floor_plane_ransac,
    align_to_gravity,
    compute_spawn_position,
)


def build_video(
    input_video: str,
    output_stella: str,
    voxel_size: float = 0.1,
    max_frames: int = 1500,
    title: str = "Video Scan",
    mast3r_path: Optional[str] = None,
    use_existing_ply: Optional[str] = None,
) -> str:
    """
    Build a .stella file from a video using MASt3R-SLAM.
    
    Args:
        input_video: Path to input video (MP4)
        output_stella: Path for output .stella file
        voxel_size: Size of each voxel in meters
        max_frames: Maximum frames to process
        title: World title
        mast3r_path: Path to MASt3R-SLAM main.py (auto-detected if None)
        use_existing_ply: Skip SLAM and use existing .ply file
    
    Returns:
        Path to created .stella file
    """
    if not HAS_TRIMESH:
        raise ImportError("trimesh is required. Install with: pip install trimesh")
    
    input_path = Path(input_video)
    output_path = Path(output_stella)
    
    if not use_existing_ply and not input_path.exists():
        raise FileNotFoundError(f"Input video not found: {input_video}")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Step 1: Run MASt3R-SLAM or use existing PLY
        if use_existing_ply:
            ply_path = Path(use_existing_ply)
            if not ply_path.exists():
                raise FileNotFoundError(f"PLY file not found: {use_existing_ply}")
            print(f"Using existing PLY: {ply_path}")
        else:
            print(f"Running MASt3R-SLAM on: {input_video}")
            ply_path = run_mast3r_slam(
                input_video, 
                str(tmpdir), 
                max_frames, 
                mast3r_path,
                no_viz=True
            )
        
        # Step 2: Load point cloud
        print("Loading point cloud...")
        points, colors = load_point_cloud(str(ply_path))
        print(f"Loaded {len(points)} points")
        
        if len(points) < 100:
            raise ValueError("Point cloud too sparse for world generation")
        
        # Step 3: Fit floor plane
        print("Fitting floor plane...")
        try:
            floor_normal, floor_point, inliers = fit_floor_plane_ransac(points)
            print(f"Floor plane found with {inliers.sum()} inliers")
        except ValueError as e:
            print(f"Warning: Could not fit floor plane: {e}")
            floor_normal = np.array([0.0, 1.0, 0.0])
            floor_point = np.array([0.0, np.percentile(points[:, 1], 5), 0.0])
        
        # Step 4: Align to gravity
        print("Aligning to gravity...")
        aligned_points, rotation = align_to_gravity(points, floor_normal, floor_point)
        
        # Shift so floor is at Y=0
        floor_y = np.percentile(aligned_points[:, 1], 5)
        aligned_points[:, 1] -= floor_y
        
        # Step 5: Voxelize
        print(f"Voxelizing with {voxel_size}m voxels...")
        grid, origin = voxelize_points(aligned_points, voxel_size, padding=2)
        print(f"Grid dimensions: {grid.shape}")
        
        # Step 6: Clean occupancy grid
        print("Cleaning occupancy grid...")
        grid = clean_occupancy_grid(grid)
        
        # Step 7: Find spawn position
        spawn_pos = compute_spawn_position(grid, voxel_size, origin)
        if spawn_pos is None:
            # Default spawn
            spawn_pos = [
                origin[0] + grid.shape[0] * voxel_size / 2,
                1.7,
                origin[2] + grid.shape[2] * voxel_size / 2,
            ]
            print("Warning: Using default spawn position")
        else:
            print(f"Spawn position: {spawn_pos}")
        
        # Step 8: Create render mesh (point cloud for now)
        print("Creating render mesh...")
        mesh = create_render_mesh_from_points(aligned_points, colors)
        
        # Write collision
        collision_path = tmpdir / "collision.rlevox"
        write_rlevox(collision_path, grid, voxel_size, origin)
        print(f"Collision: {grid.sum()} solid voxels")
        
        # Write render
        render_path = tmpdir / "render.glb"
        mesh.export(str(render_path))
        print(f"Render mesh: {len(mesh.vertices)} vertices")
        
        # Create level.json
        level_json = make_level_json(
            name="Scanned Space",
            spawn_position=spawn_pos,
            player_height=1.7,
        )
        level_json.capture = {
            "source": "video_slam",
            "notes": f"Generated from {input_path.name}",
        }
        
        # Create manifest
        manifest = make_manifest(
            title=title,
            tags=["video-scan", "mast3r-slam"],
        )
        
        # Pack stella
        file_map = {
            "levels/0/level.json": level_json.to_json().encode("utf-8"),
            "levels/0/render.glb": render_path.read_bytes(),
            "levels/0/collision.rlevox": collision_path.read_bytes(),
        }
        
        output_path = pack_stella(output_stella, manifest, file_map)
        print(f"Created: {output_path}")
    
    return str(output_path)


def run_mast3r_slam(
    input_video: str,
    output_dir: str,
    max_frames: int,
    mast3r_path: Optional[str] = None,
    no_viz: bool = True,
) -> str:
    """
    Run MASt3R-SLAM on a video file.
    
    Args:
        input_video: Path to input video
        output_dir: Directory for outputs (PLY will be saved here)
        max_frames: Maximum frames to process (used for subsampling)
        mast3r_path: Path to MASt3R-SLAM root directory (auto-detected if None)
        no_viz: Disable visualization window
    
    Returns:
        Path to output PLY file
    """
    # Find MASt3R-SLAM
    if mast3r_path is None:
        # Try to find it relative to this package
        possible_paths = [
            Path(__file__).parent.parent.parent.parent,  # Up 4 levels to MASt3R-SLAM-main 2
            Path(__file__).parent.parent.parent,  # Up 3 levels  
            Path.cwd(),
        ]
        
        for p in possible_paths:
            main_py = p / "main.py"
            if main_py.exists() and (p / "mast3r_slam").exists():
                mast3r_path = str(p)
                break
        
        if mast3r_path is None:
            raise FileNotFoundError(
                "Could not find MASt3R-SLAM. "
                "Please specify path with --mast3r-path"
            )
    
    mast3r_root = Path(mast3r_path)
    main_script = mast3r_root / "main.py"
    
    if not main_script.exists():
        raise FileNotFoundError(f"main.py not found at: {main_script}")
    
    print(f"Using MASt3R-SLAM at: {mast3r_root}")
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Determine output filename (video basename)
    video_name = Path(input_video).stem
    
    # Build command - MASt3R-SLAM expects:
    # python main.py --dataset <path_to_video.mp4> --save-as <name> [--no-viz] [--config <config>]
    cmd = [
        sys.executable,
        str(main_script),
        "--dataset", str(input_video),
        "--save-as", video_name,
        "--config", str(mast3r_root / "config" / "base.yaml"),
    ]
    
    if no_viz:
        cmd.append("--no-viz")
    
    print(f"Running: {' '.join(cmd)}")
    print("This may take several minutes depending on video length...")
    
    # Run MASt3R-SLAM
    env = os.environ.copy()
    env["PYTHONPATH"] = str(mast3r_root) + ":" + env.get("PYTHONPATH", "")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(mast3r_root),
            env=env,
            check=True,
            capture_output=False,  # Show output in real-time
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"MASt3R-SLAM failed with exit code: {e.returncode}")
    
    # Find output PLY - it's saved to logs/{save-as}/{video_name}.ply
    ply_candidates = [
        mast3r_root / "logs" / video_name / f"{video_name}.ply",
        mast3r_root / "logs" / "default" / f"{video_name}.ply",
        mast3r_root / "logs" / "base" / f"{video_name}.ply",
        output_path / f"{video_name}.ply",
    ]
    
    for ply_path in ply_candidates:
        if ply_path.exists():
            print(f"Found PLY output: {ply_path}")
            return str(ply_path)
    
    # Search for any PLY file
    for ply in mast3r_root.glob("logs/**/*.ply"):
        if video_name in ply.name:
            print(f"Found PLY output: {ply}")
            return str(ply)
    
    raise FileNotFoundError(
        f"Could not find output PLY for {video_name}. "
        f"Check logs/ directory in {mast3r_root}"
    )


def load_point_cloud(ply_path: str) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """
    Load a point cloud from PLY file.
    
    Args:
        ply_path: Path to PLY file
    
    Returns:
        Tuple of (points, colors) arrays
    """
    mesh = trimesh.load(ply_path)
    
    if hasattr(mesh, 'vertices'):
        points = np.array(mesh.vertices)
    else:
        points = np.array(mesh)
    
    colors = None
    if hasattr(mesh, 'colors'):
        colors = np.array(mesh.colors)[:, :3]  # RGB only
    elif hasattr(mesh, 'visual') and hasattr(mesh.visual, 'vertex_colors'):
        colors = np.array(mesh.visual.vertex_colors)[:, :3]
    
    return points, colors


def clean_occupancy_grid(grid: np.ndarray) -> np.ndarray:
    """
    Clean up an occupancy grid by removing noise.
    
    Args:
        grid: 3D boolean array
    
    Returns:
        Cleaned grid
    """
    try:
        from scipy import ndimage
        
        # Remove small floating components
        labeled, num_features = ndimage.label(grid)
        if num_features > 0:
            component_sizes = ndimage.sum(grid, labeled, range(1, num_features + 1))
            
            # Keep components larger than threshold
            min_size = max(10, grid.sum() * 0.001)  # At least 0.1% of total
            
            cleaned = np.zeros_like(grid)
            for i, size in enumerate(component_sizes, 1):
                if size >= min_size:
                    cleaned |= (labeled == i)
            
            return cleaned
        
    except ImportError:
        pass  # scipy not available, skip cleaning
    
    return grid


def create_render_mesh_from_points(
    points: np.ndarray,
    colors: Optional[np.ndarray] = None,
) -> "trimesh.Trimesh":
    """
    Create a render mesh from point cloud.
    
    For MVP, creates point cloud visualization.
    Future: Poisson/ball-pivoting reconstruction.
    
    Args:
        points: Nx3 array of points
        colors: Optional Nx3 array of RGB colors (0-255)
    
    Returns:
        trimesh object
    """
    # Create point cloud as tiny spheres for GLB export
    # (GLB doesn't directly support point clouds)
    
    # For efficiency, subsample if too many points
    max_points = 50000
    if len(points) > max_points:
        indices = np.random.choice(len(points), max_points, replace=False)
        points = points[indices]
        if colors is not None:
            colors = colors[indices]
    
    # Create small icospheres at each point
    sphere = trimesh.creation.icosphere(subdivisions=0, radius=0.01)
    
    meshes = []
    for i, pt in enumerate(points):
        s = sphere.copy()
        s.apply_translation(pt)
        
        if colors is not None:
            color = colors[i]
            if color.max() <= 1.0:
                color = (color * 255).astype(np.uint8)
            s.visual.vertex_colors = np.tile(
                np.append(color, 255),
                (len(s.vertices), 1)
            )
        
        meshes.append(s)
    
    # Combine all spheres
    if meshes:
        combined = trimesh.util.concatenate(meshes)
    else:
        combined = trimesh.Trimesh()
    
    return combined


def estimate_scale_from_video(video_path: str) -> float:
    """
    Estimate real-world scale from video metadata or content.
    
    For now, returns default scale. Future: use depth estimation
    or known object detection.
    
    Args:
        video_path: Path to video
    
    Returns:
        Estimated scale factor (meters per unit)
    """
    # Default: assume 1 unit = 1 meter
    return 1.0
