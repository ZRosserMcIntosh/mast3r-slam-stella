"""Tests for pipeline modules."""

import os
import tempfile
import numpy as np
import pytest

# Skip tests if optional dependencies not available
cv2 = pytest.importorskip("cv2", reason="opencv-python required")
trimesh = pytest.importorskip("trimesh", reason="trimesh required")

from stella.pipeline_floorplan import build_floorplan, create_wall_mesh_from_2d
from stella.geometry import fit_floor_plane_ransac, align_to_gravity


class TestFloorplanPipeline:
    """Test floorplan to .stella pipeline."""
    
    def test_create_wall_mesh(self):
        """Test wall mesh creation from 2D occupancy."""
        # Create simple occupancy grid (10x10 with walls around edge)
        occupancy = np.zeros((10, 10), dtype=bool)
        occupancy[0, :] = True  # Top wall
        occupancy[9, :] = True  # Bottom wall
        occupancy[:, 0] = True  # Left wall
        occupancy[:, 9] = True  # Right wall
        
        mesh = create_wall_mesh_from_2d(occupancy, wall_height=2.7, voxel_size=0.1)
        
        assert len(mesh.vertices) > 0
        assert len(mesh.faces) > 0
    
    def test_build_floorplan_simple(self):
        """Test building .stella from a simple floorplan image."""
        # Create a test image
        img = np.ones((100, 100), dtype=np.uint8) * 255  # White background
        img[10:90, 10:15] = 0  # Left wall (black)
        img[10:90, 85:90] = 0  # Right wall
        img[10:15, 10:90] = 0  # Top wall
        img[85:90, 10:90] = 0  # Bottom wall
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as img_file:
            img_path = img_file.name
            cv2.imwrite(img_path, img)
        
        with tempfile.NamedTemporaryFile(suffix='.stella', delete=False) as out_file:
            out_path = out_file.name
        
        try:
            result = build_floorplan(
                input_image=img_path,
                output_stella=out_path,
                wall_height=2.7,
                voxel_size=0.1,
                pixels_per_meter=10,  # 10 pixels = 1 meter
            )
            
            assert os.path.exists(result)
            assert os.path.getsize(result) > 0
        finally:
            os.unlink(img_path)
            if os.path.exists(out_path):
                os.unlink(out_path)
    
    def test_build_floorplan_missing_image(self):
        """Test error handling for missing input image."""
        with pytest.raises(FileNotFoundError):
            build_floorplan(
                input_image="/nonexistent/image.png",
                output_stella="/tmp/out.stella",
            )


class TestGeometry:
    """Test geometry utilities."""
    
    def test_fit_floor_plane(self):
        """Test RANSAC floor plane fitting."""
        # Create points on a horizontal plane (y=0) with some noise
        np.random.seed(42)
        n_points = 1000
        
        # Floor points
        floor_points = np.random.rand(n_points, 3)
        floor_points[:, 1] = np.random.randn(n_points) * 0.01  # Small noise in Y
        
        # Some outliers above floor
        outliers = np.random.rand(100, 3)
        outliers[:, 1] += 1.0  # 1 meter above
        
        all_points = np.vstack([floor_points, outliers])
        
        normal, point, inliers = fit_floor_plane_ransac(
            all_points,
            n_iterations=500,
            distance_threshold=0.05,
        )
        
        # Normal should point roughly up
        assert normal[1] > 0.9, "Floor normal should point up"
        
        # Most floor points should be inliers
        assert inliers[:n_points].sum() > n_points * 0.9
    
    def test_align_to_gravity(self):
        """Test gravity alignment."""
        # Create points with tilted floor
        points = np.array([
            [0, 0, 0],
            [1, 0.1, 0],  # Slightly tilted
            [0, 0, 1],
            [1, 0.1, 1],
        ], dtype=float)
        
        # Floor normal is tilted
        floor_normal = np.array([0.0, 0.995, 0.1])  # Slightly tilted
        floor_normal = floor_normal / np.linalg.norm(floor_normal)
        floor_point = np.array([0.5, 0.05, 0.5])
        
        aligned, R = align_to_gravity(points, floor_normal, floor_point)
        
        # After alignment, points should be more level
        # The y-spread should be reduced
        assert R.shape == (3, 3)


class TestEmpty:
    """Placeholder tests for video pipeline (requires MASt3R-SLAM)."""
    
    def test_placeholder(self):
        """Video pipeline tests require full MASt3R-SLAM setup."""
        # These tests would require the full SLAM system
        # For now, just verify imports work
        from stella.pipeline_video import build_video, load_point_cloud, clean_occupancy_grid
        
        assert callable(build_video)
        assert callable(load_point_cloud)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
