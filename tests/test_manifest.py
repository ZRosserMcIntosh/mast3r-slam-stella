"""Tests for manifest.py - Manifest and LevelJson dataclasses."""

import json
import pytest

from stella.manifest import (
    Manifest, LevelJson, Level, World, Axis, Generator,
    Spawn, RenderAsset, CollisionAsset, PlayerCollision,
    make_manifest, make_level_json,
)


class TestManifest:
    """Test Manifest dataclass."""
    
    def test_default_manifest(self):
        """Test creating manifest with defaults."""
        manifest = Manifest()
        
        assert manifest.format == "stella.world"
        assert manifest.version == 1
        assert manifest.units == "meters"
        assert manifest.axis.up == "Y"
        assert manifest.axis.handedness == "right"
    
    def test_manifest_to_json(self):
        """Test manifest JSON serialization."""
        manifest = Manifest(
            levels=[Level(id="0", path="levels/0/level.json", name="Floor 0")],
            world=World(title="Test World"),
        )
        
        json_str = manifest.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["format"] == "stella.world"
        assert parsed["version"] == 1
        assert len(parsed["levels"]) == 1
        assert parsed["levels"][0]["id"] == "0"
    
    def test_manifest_from_json(self):
        """Test manifest JSON deserialization."""
        json_str = '''
        {
            "format": "stella.world",
            "version": 1,
            "created_utc": "2025-12-15T00:00:00Z",
            "units": "meters",
            "axis": {"up": "Y", "forward": "-Z", "handedness": "right"},
            "levels": [{"id": "0", "path": "levels/0/level.json"}],
            "world": {"title": "Loaded World", "tags": ["test"], "privacy": {}}
        }
        '''
        
        manifest = Manifest.from_json(json_str)
        
        assert manifest.format == "stella.world"
        assert manifest.world.title == "Loaded World"
        assert manifest.levels[0].id == "0"
    
    def test_manifest_roundtrip(self):
        """Test JSON serialization roundtrip."""
        original = Manifest(
            levels=[Level(id="0", path="levels/0/level.json")],
            generator=Generator(name="test", version="1.0.0"),
            world=World(title="Roundtrip Test", tags=["a", "b"]),
        )
        
        json_str = original.to_json()
        restored = Manifest.from_json(json_str)
        
        assert restored.format == original.format
        assert restored.world.title == original.world.title
        assert restored.generator.name == original.generator.name
    
    def test_manifest_validation_valid(self):
        """Test validation passes for valid manifest."""
        manifest = Manifest(
            levels=[Level(id="0", path="levels/0/level.json")],
        )
        
        errors = manifest.validate()
        assert len(errors) == 0
    
    def test_manifest_validation_no_levels(self):
        """Test validation fails when no levels."""
        manifest = Manifest(levels=[])
        
        errors = manifest.validate()
        assert any("at least one level" in e for e in errors)
    
    def test_manifest_validation_wrong_format(self):
        """Test validation fails for wrong format."""
        manifest = Manifest(
            format="wrong.format",
            levels=[Level(id="0", path="test")],
        )
        
        errors = manifest.validate()
        assert any("Invalid format" in e for e in errors)


class TestLevelJson:
    """Test LevelJson dataclass."""
    
    def test_default_level(self):
        """Test creating level with defaults."""
        level = LevelJson()
        
        assert level.level_version == 1
        assert level.name == "Level 0"
        assert level.spawn.position == [0.0, 1.7, 0.0]
        assert level.collision.player.height_m == 1.7
    
    def test_level_to_json(self):
        """Test level JSON serialization."""
        level = LevelJson(
            name="Custom Level",
            spawn=Spawn(position=[5.0, 1.7, 10.0], yaw_degrees=90.0),
        )
        
        json_str = level.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["name"] == "Custom Level"
        assert parsed["spawn"]["position"] == [5.0, 1.7, 10.0]
        assert parsed["spawn"]["yaw_degrees"] == 90.0
    
    def test_level_from_json(self):
        """Test level JSON deserialization."""
        json_str = '''
        {
            "level_version": 1,
            "name": "Loaded Level",
            "scale": {"meters_per_unit": 1.0},
            "spawn": {"position": [0, 0, 0], "yaw_degrees": 0},
            "render": {"type": "glb", "uri": "render.glb"},
            "collision": {
                "type": "rlevox",
                "uri": "collision.rlevox",
                "player": {"height_m": 1.8, "radius_m": 0.3, "step_height_m": 0.35}
            },
            "navigation": {"type": "none"}
        }
        '''
        
        level = LevelJson.from_json(json_str)
        
        assert level.name == "Loaded Level"
        assert level.collision.player.height_m == 1.8
    
    def test_level_roundtrip(self):
        """Test JSON serialization roundtrip."""
        original = LevelJson(
            name="Roundtrip Level",
            spawn=Spawn(position=[1.0, 2.0, 3.0]),
            collision=CollisionAsset(
                player=PlayerCollision(height_m=1.9, radius_m=0.4)
            ),
        )
        
        json_str = original.to_json()
        restored = LevelJson.from_json(json_str)
        
        assert restored.name == original.name
        assert restored.spawn.position == original.spawn.position
        assert restored.collision.player.height_m == 1.9


class TestMakeManifest:
    """Test make_manifest helper."""
    
    def test_make_manifest_defaults(self):
        """Test make_manifest with defaults."""
        manifest = make_manifest()
        
        assert manifest.format == "stella.world"
        assert manifest.world.title == "Untitled World"
        assert len(manifest.levels) == 1
        assert manifest.generator is not None
    
    def test_make_manifest_custom(self):
        """Test make_manifest with custom values."""
        manifest = make_manifest(
            title="Custom World",
            tags=["tag1", "tag2"],
            thumbnail="thumbs/cover.jpg",
        )
        
        assert manifest.world.title == "Custom World"
        assert manifest.world.tags == ["tag1", "tag2"]
        assert manifest.assets["thumbnail"] == "thumbs/cover.jpg"
    
    def test_make_manifest_custom_levels(self):
        """Test make_manifest with custom levels."""
        levels = [
            Level(id="0", path="levels/0/level.json", name="Ground Floor"),
            Level(id="1", path="levels/1/level.json", name="First Floor"),
        ]
        
        manifest = make_manifest(title="Multi-Floor", levels=levels)
        
        assert len(manifest.levels) == 2
        assert manifest.levels[1].name == "First Floor"


class TestMakeLevelJson:
    """Test make_level_json helper."""
    
    def test_make_level_defaults(self):
        """Test make_level_json with defaults."""
        level = make_level_json()
        
        assert level.name == "Level 0"
        assert level.spawn.position[1] == 1.7  # Player height
        assert level.render.uri == "render.glb"
        assert level.collision.uri == "collision.rlevox"
    
    def test_make_level_custom(self):
        """Test make_level_json with custom values."""
        level = make_level_json(
            name="Custom Level",
            spawn_position=[10.0, 1.5, 20.0],
            player_height=1.5,
            render_uri="custom_render.glb",
        )
        
        assert level.name == "Custom Level"
        assert level.spawn.position == [10.0, 1.5, 20.0]
        assert level.collision.player.height_m == 1.5
        assert level.render.uri == "custom_render.glb"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
