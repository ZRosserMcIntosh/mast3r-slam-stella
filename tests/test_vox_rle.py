"""Tests for vox_rle.py - RLEVOX format read/write."""

import numpy as np
import os
import tempfile
import pytest

from stella.vox_rle import write_rlevox, read_rlevox, voxelize_points, grid_to_world, world_to_grid


class TestRLEVOXReadWrite:
    """Test basic RLEVOX file I/O."""
    
    def test_write_read_roundtrip(self):
        """Test that write then read returns identical data."""
        voxel_size = 0.1
        origin = (0.0, 0.0, 0.0)
        grid = np.zeros((10, 10, 10), dtype=bool)
        grid[2:8, 2:8, 2:8] = True  # Solid cube
        
        with tempfile.NamedTemporaryFile(suffix='.rlevox', delete=False) as f:
            path = f.name
        
        try:
            write_rlevox(path, grid, voxel_size, origin)
            read_grid, read_voxel_size, read_origin = read_rlevox(path)
            
            assert np.array_equal(grid, read_grid)
            assert abs(voxel_size - read_voxel_size) < 1e-6  # Float32 precision
            assert tuple(abs(a - b) < 1e-6 for a, b in zip(origin, read_origin))
        finally:
            os.unlink(path)
    
    def test_empty_grid(self):
        """Test with completely empty grid."""
        voxel_size = 0.1
        origin = (0.0, 0.0, 0.0)
        grid = np.zeros((5, 5, 5), dtype=bool)
        
        with tempfile.NamedTemporaryFile(suffix='.rlevox', delete=False) as f:
            path = f.name
        
        try:
            write_rlevox(path, grid, voxel_size, origin)
            read_grid, _, _ = read_rlevox(path)
            
            assert np.array_equal(grid, read_grid)
            assert read_grid.sum() == 0
        finally:
            os.unlink(path)
    
    def test_full_grid(self):
        """Test with completely solid grid."""
        voxel_size = 0.1
        origin = (1.0, 2.0, 3.0)
        grid = np.ones((5, 5, 5), dtype=bool)
        
        with tempfile.NamedTemporaryFile(suffix='.rlevox', delete=False) as f:
            path = f.name
        
        try:
            write_rlevox(path, grid, voxel_size, origin)
            read_grid, read_voxel_size, read_origin = read_rlevox(path)
            
            assert np.array_equal(grid, read_grid)
            assert read_origin == (1.0, 2.0, 3.0)
        finally:
            os.unlink(path)
    
    def test_random_grid(self):
        """Test with random pattern."""
        voxel_size = 0.05
        origin = (-5.0, 0.0, -5.0)
        np.random.seed(42)
        grid = np.random.choice([True, False], size=(20, 15, 20))
        
        with tempfile.NamedTemporaryFile(suffix='.rlevox', delete=False) as f:
            path = f.name
        
        try:
            write_rlevox(path, grid, voxel_size, origin)
            read_grid, _, _ = read_rlevox(path)
            
            assert np.array_equal(grid, read_grid)
        finally:
            os.unlink(path)
    
    def test_large_grid(self):
        """Test with larger grid to verify RLE efficiency."""
        voxel_size = 0.1
        origin = (0.0, 0.0, 0.0)
        grid = np.zeros((100, 50, 100), dtype=bool)
        # Create some walls
        grid[0:5, :, :] = True
        grid[95:100, :, :] = True
        grid[:, :, 0:5] = True
        grid[:, :, 95:100] = True
        
        with tempfile.NamedTemporaryFile(suffix='.rlevox', delete=False) as f:
            path = f.name
        
        try:
            write_rlevox(path, grid, voxel_size, origin)
            
            # File should be relatively small due to RLE compression
            file_size = os.path.getsize(path)
            raw_size = grid.size  # 1 byte per voxel uncompressed
            assert file_size < raw_size, "RLE should compress walls efficiently"
            
            read_grid, _, _ = read_rlevox(path)
            assert np.array_equal(grid, read_grid)
        finally:
            os.unlink(path)


class TestVoxelizePoints:
    """Test point cloud voxelization."""
    
    def test_basic_voxelization(self):
        """Test voxelizing a simple point cloud."""
        points = np.array([
            [0.0, 0.0, 0.0],
            [0.5, 0.5, 0.5],
            [1.0, 1.0, 1.0],
        ])
        
        grid, origin = voxelize_points(points, voxel_size=0.5, padding=1)
        
        assert grid.ndim == 3
        assert grid.sum() == 3  # 3 points = 3 occupied voxels
    
    def test_empty_points(self):
        """Test voxelizing empty point array."""
        points = np.array([]).reshape(0, 3)
        
        grid, origin = voxelize_points(points, voxel_size=0.1)
        
        assert grid.shape == (1, 1, 1)
        assert grid.sum() == 0


class TestCoordinateConversion:
    """Test grid<->world coordinate conversion."""
    
    def test_grid_to_world(self):
        """Test converting grid indices to world coordinates."""
        voxel_size = 0.1
        origin = (0.0, 0.0, 0.0)
        
        indices = np.array([[0, 0, 0], [10, 5, 10]])
        world_coords = grid_to_world(indices, voxel_size, origin)
        
        # Voxel center should be at (index + 0.5) * voxel_size + origin
        expected = np.array([
            [0.05, 0.05, 0.05],
            [1.05, 0.55, 1.05],
        ])
        np.testing.assert_array_almost_equal(world_coords, expected)
    
    def test_world_to_grid(self):
        """Test converting world coordinates to grid indices."""
        voxel_size = 0.1
        origin = (0.0, 0.0, 0.0)
        
        positions = np.array([[0.05, 0.05, 0.05], [1.0, 0.5, 1.0]])
        indices = world_to_grid(positions, voxel_size, origin)
        
        expected = np.array([[0, 0, 0], [10, 5, 10]])
        np.testing.assert_array_equal(indices, expected)
    
    def test_roundtrip_conversion(self):
        """Test grid->world->grid roundtrip."""
        voxel_size = 0.2
        origin = (1.0, 2.0, 3.0)
        
        original_indices = np.array([[5, 10, 15], [0, 0, 0], [99, 49, 99]])
        
        world = grid_to_world(original_indices, voxel_size, origin)
        back_to_grid = world_to_grid(world, voxel_size, origin)
        
        np.testing.assert_array_equal(original_indices, back_to_grid)


class TestInvalidInput:
    """Test error handling for invalid inputs."""
    
    def test_invalid_magic(self):
        """Test reading file with invalid magic number."""
        with tempfile.NamedTemporaryFile(suffix='.rlevox', delete=False) as f:
            f.write(b"XXXX")  # Wrong magic
            path = f.name
        
        try:
            with pytest.raises(ValueError, match="Invalid magic"):
                read_rlevox(path)
        finally:
            os.unlink(path)
    
    def test_non_3d_grid(self):
        """Test writing non-3D array."""
        grid_2d = np.zeros((10, 10), dtype=bool)
        
        with tempfile.NamedTemporaryFile(suffix='.rlevox', delete=False) as f:
            path = f.name
        
        try:
            with pytest.raises(ValueError, match="3D"):
                write_rlevox(path, grid_2d, 0.1, (0, 0, 0))
        finally:
            if os.path.exists(path):
                os.unlink(path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
