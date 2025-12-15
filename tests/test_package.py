"""Tests for package.py - .stella packaging."""

import os
import tempfile
import pytest

from stella.package import (
    pack_stella, unpack_stella, get_stella_info,
    verify_stella_checksums, read_stella_file, compute_sha256,
)
from stella.manifest import make_manifest, make_level_json


class TestPackStella:
    """Test .stella packaging."""
    
    def test_basic_pack_unpack(self):
        """Test basic pack and unpack roundtrip."""
        manifest = make_manifest(title="Test World")
        level_json = make_level_json(name="Test Level")
        
        file_map = {
            "levels/0/level.json": level_json.to_json().encode("utf-8"),
            "levels/0/render.glb": b"fake glb data",
            "levels/0/collision.rlevox": b"fake collision data",
        }
        
        with tempfile.NamedTemporaryFile(suffix='.stella', delete=False) as f:
            path = f.name
        
        try:
            pack_stella(path, manifest, file_map)
            
            # Verify file exists
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0
            
            # Unpack and verify
            unpacked_manifest, zf = unpack_stella(path)
            
            assert unpacked_manifest.format == "stella.world"
            assert unpacked_manifest.version == 1
            assert unpacked_manifest.world.title == "Test World"
            assert len(unpacked_manifest.levels) == 1
            
            zf.close()
        finally:
            os.unlink(path)
    
    def test_pack_with_dict_manifest(self):
        """Test packing with dict manifest instead of Manifest object."""
        manifest_dict = {
            "format": "stella.world",
            "version": 1,
            "created_utc": "2025-12-15T00:00:00Z",
            "units": "meters",
            "axis": {"up": "Y", "forward": "-Z", "handedness": "right"},
            "levels": [{"id": "0", "path": "levels/0/level.json"}],
        }
        
        file_map = {
            "levels/0/level.json": b"{}",
        }
        
        with tempfile.NamedTemporaryFile(suffix='.stella', delete=False) as f:
            path = f.name
        
        try:
            pack_stella(path, manifest_dict, file_map)
            manifest, zf = unpack_stella(path)
            
            assert manifest.format == "stella.world"
            zf.close()
        finally:
            os.unlink(path)
    
    def test_checksums(self):
        """Test that checksums are generated and verifiable."""
        manifest = make_manifest(title="Checksum Test")
        file_map = {
            "levels/0/level.json": b'{"test": "data"}',
        }
        
        with tempfile.NamedTemporaryFile(suffix='.stella', delete=False) as f:
            path = f.name
        
        try:
            pack_stella(path, manifest, file_map, include_checksums=True)
            
            valid, errors = verify_stella_checksums(path)
            assert valid, f"Checksum verification failed: {errors}"
        finally:
            os.unlink(path)
    
    def test_no_checksums(self):
        """Test packing without checksums."""
        manifest = make_manifest(title="No Checksum Test")
        file_map = {"levels/0/level.json": b"{}"}
        
        with tempfile.NamedTemporaryFile(suffix='.stella', delete=False) as f:
            path = f.name
        
        try:
            pack_stella(path, manifest, file_map, include_checksums=False)
            
            valid, errors = verify_stella_checksums(path)
            assert valid  # Should pass (no checksums to verify)
            assert "No checksums" in errors[0]
        finally:
            os.unlink(path)


class TestUnpackStella:
    """Test .stella unpacking."""
    
    def test_unpack_to_directory(self):
        """Test extracting .stella to a directory."""
        manifest = make_manifest(title="Extract Test")
        file_map = {
            "levels/0/level.json": b'{"name": "test"}',
            "levels/0/render.glb": b"glb data here",
        }
        
        with tempfile.NamedTemporaryFile(suffix='.stella', delete=False) as f:
            stella_path = f.name
        
        with tempfile.TemporaryDirectory() as extract_dir:
            try:
                pack_stella(stella_path, manifest, file_map)
                
                manifest, zf = unpack_stella(stella_path, extract_to=extract_dir)
                zf.close()
                
                # Verify extracted files
                assert os.path.exists(os.path.join(extract_dir, "manifest.json"))
                assert os.path.exists(os.path.join(extract_dir, "levels", "0", "level.json"))
                assert os.path.exists(os.path.join(extract_dir, "levels", "0", "render.glb"))
            finally:
                os.unlink(stella_path)
    
    def test_invalid_stella_missing_manifest(self):
        """Test that missing manifest raises error."""
        import zipfile
        
        with tempfile.NamedTemporaryFile(suffix='.stella', delete=False) as f:
            path = f.name
        
        try:
            # Create invalid .stella (zip without manifest.json)
            with zipfile.ZipFile(path, 'w') as zf:
                zf.writestr("some_file.txt", "no manifest here")
            
            with pytest.raises(ValueError, match="missing manifest.json"):
                unpack_stella(path)
        finally:
            os.unlink(path)


class TestGetStellaInfo:
    """Test info retrieval."""
    
    def test_get_info(self):
        """Test getting stella file info."""
        manifest = make_manifest(title="Info Test", tags=["test", "unit"])
        file_map = {
            "levels/0/level.json": b"level data " * 100,
            "levels/0/render.glb": b"render data " * 1000,
        }
        
        with tempfile.NamedTemporaryFile(suffix='.stella', delete=False) as f:
            path = f.name
        
        try:
            pack_stella(path, manifest, file_map)
            
            info = get_stella_info(path)
            
            assert info["manifest"]["format"] == "stella.world"
            assert info["manifest"]["world"]["title"] == "Info Test"
            assert len(info["files"]) > 0
            assert info["total_uncompressed_size"] > 0
            assert info["archive_size"] > 0
        finally:
            os.unlink(path)


class TestReadStellaFile:
    """Test reading individual files from .stella."""
    
    def test_read_single_file(self):
        """Test reading a single file from the archive."""
        manifest = make_manifest(title="Read Test")
        test_data = b"specific file content here"
        file_map = {
            "levels/0/level.json": test_data,
        }
        
        with tempfile.NamedTemporaryFile(suffix='.stella', delete=False) as f:
            path = f.name
        
        try:
            pack_stella(path, manifest, file_map)
            
            content = read_stella_file(path, "levels/0/level.json")
            assert content == test_data
        finally:
            os.unlink(path)


class TestComputeSha256:
    """Test SHA256 computation."""
    
    def test_known_hash(self):
        """Test SHA256 against known value."""
        # SHA256 of empty string
        empty_hash = compute_sha256(b"")
        assert empty_hash == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        
        # SHA256 of "hello"
        hello_hash = compute_sha256(b"hello")
        assert hello_hash == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


class TestValidateStella:
    """Test .stella validation."""
    
    def test_validate_valid_stella(self):
        """Test validation of a properly structured .stella file."""
        from stella.package import validate_stella
        
        manifest = make_manifest(title="Valid Test")
        file_map = {
            "levels/0/level.json": b'{"name": "Test Level"}',
            "levels/0/render.glb": b"GLB_DATA",
            "levels/0/collision.rlevox": b"VOX_DATA",
        }
        
        with tempfile.NamedTemporaryFile(suffix='.stella', delete=False) as f:
            path = f.name
        
        try:
            pack_stella(path, manifest, file_map)
            
            valid, errors = validate_stella(path)
            assert valid, f"Expected valid, got errors: {errors}"
            assert errors == []
        finally:
            os.unlink(path)
    
    def test_validate_missing_files(self):
        """Test validation catches missing required files."""
        from stella.package import validate_stella
        
        manifest = make_manifest(title="Missing Files Test")
        # Missing render.glb and collision.rlevox
        file_map = {
            "levels/0/level.json": b'{"name": "Test Level"}',
        }
        
        with tempfile.NamedTemporaryFile(suffix='.stella', delete=False) as f:
            path = f.name
        
        try:
            pack_stella(path, manifest, file_map)
            
            valid, errors = validate_stella(path)
            assert not valid, "Expected invalid due to missing files"
            assert len(errors) == 2  # Missing render.glb and collision.rlevox
            assert any("render.glb" in e for e in errors)
            assert any("collision.rlevox" in e for e in errors)
        finally:
            os.unlink(path)
    
    def test_validate_nonexistent_file(self):
        """Test validation of non-existent file."""
        from stella.package import validate_stella
        
        valid, errors = validate_stella("/nonexistent/path/to/file.stella")
        assert not valid
        assert any("not found" in e.lower() for e in errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
