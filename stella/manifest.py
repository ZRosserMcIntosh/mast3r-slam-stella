"""
Manifest and level JSON creation/validation for .stella files.

This module provides dataclasses and helpers for creating and validating
the manifest.json and level.json files required in .stella packages.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import json
from datetime import datetime, timezone


@dataclass
class Axis:
    """Coordinate system definition."""
    up: str = "Y"
    forward: str = "-Z"
    handedness: str = "right"


@dataclass
class Generator:
    """Build tool information."""
    name: str = "stella-cli"
    version: str = "0.1.0"
    git_commit: Optional[str] = None


@dataclass
class World:
    """World-level metadata."""
    title: str = "Untitled World"
    tags: List[str] = field(default_factory=list)
    privacy: Dict[str, Any] = field(default_factory=lambda: {"contains_source_media": False})


@dataclass
class Level:
    """Reference to a level within the package."""
    id: str
    path: str
    name: Optional[str] = None


@dataclass
class Manifest:
    """
    Main manifest.json structure for .stella files.
    
    Required fields:
    - format: Must be "stella.world"
    - version: Format version (currently 1)
    - created_utc: ISO 8601 timestamp
    - units: Measurement units (default "meters")
    - axis: Coordinate system definition
    - levels: List of level references
    """
    format: str = "stella.world"
    version: int = 1
    created_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    units: str = "meters"
    axis: Axis = field(default_factory=Axis)
    levels: List[Level] = field(default_factory=list)
    generator: Optional[Generator] = None
    world: Optional[World] = None
    assets: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = {
            "format": self.format,
            "version": self.version,
            "created_utc": self.created_utc,
            "units": self.units,
            "axis": asdict(self.axis),
            "levels": [
                {k: v for k, v in asdict(lvl).items() if v is not None}
                for lvl in self.levels
            ],
        }
        if self.generator:
            gen = asdict(self.generator)
            d["generator"] = {k: v for k, v in gen.items() if v is not None}
        if self.world:
            d["world"] = asdict(self.world)
        if self.assets:
            d["assets"] = self.assets
        return d

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Manifest":
        """Create Manifest from dictionary."""
        axis = Axis(**d.get("axis", {}))
        levels = [Level(**lvl) for lvl in d.get("levels", [])]
        
        generator = None
        if "generator" in d and d["generator"]:
            generator = Generator(**d["generator"])
        
        world = None
        if "world" in d and d["world"]:
            world = World(**d["world"])
        
        return cls(
            format=d.get("format", "stella.world"),
            version=d.get("version", 1),
            created_utc=d.get("created_utc", datetime.now(timezone.utc).isoformat()),
            units=d.get("units", "meters"),
            axis=axis,
            levels=levels,
            generator=generator,
            world=world,
            assets=d.get("assets", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Manifest":
        """Create Manifest from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def validate(self) -> List[str]:
        """
        Validate manifest for required fields and consistency.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if self.format != "stella.world":
            errors.append(f"Invalid format: {self.format}, expected 'stella.world'")
        
        if self.version != 1:
            errors.append(f"Unsupported version: {self.version}, expected 1")
        
        if not self.levels:
            errors.append("Manifest must contain at least one level")
        
        for lvl in self.levels:
            if not lvl.id:
                errors.append("Level missing required 'id' field")
            if not lvl.path:
                errors.append(f"Level {lvl.id} missing required 'path' field")
        
        if self.axis.up not in ["Y", "Z"]:
            errors.append(f"Invalid up axis: {self.axis.up}")
        
        if self.axis.handedness not in ["left", "right"]:
            errors.append(f"Invalid handedness: {self.axis.handedness}")
        
        return errors


@dataclass
class PlayerCollision:
    """Player collision capsule parameters."""
    height_m: float = 1.7
    radius_m: float = 0.3
    step_height_m: float = 0.35


@dataclass
class Spawn:
    """Spawn point definition."""
    position: List[float] = field(default_factory=lambda: [0.0, 1.7, 0.0])
    yaw_degrees: float = 0.0


@dataclass
class RenderAsset:
    """Render asset reference."""
    type: str = "glb"
    uri: str = "render.glb"


@dataclass
class CollisionAsset:
    """Collision asset reference."""
    type: str = "rlevox"
    uri: str = "collision.rlevox"
    player: PlayerCollision = field(default_factory=PlayerCollision)


@dataclass
class NavigationAsset:
    """Navigation asset reference."""
    type: str = "none"
    uri: Optional[str] = None


@dataclass
class CaptureInfo:
    """Source capture metadata."""
    source: str = "unknown"
    source_fps: Optional[int] = None
    notes: Optional[str] = None


@dataclass
class LevelJson:
    """
    Level definition (levels/<n>/level.json).
    
    Defines spawn point, render assets, collision, and navigation for one level.
    """
    level_version: int = 1
    name: str = "Level 0"
    scale: Dict[str, float] = field(default_factory=lambda: {"meters_per_unit": 1.0})
    spawn: Spawn = field(default_factory=Spawn)
    render: RenderAsset = field(default_factory=RenderAsset)
    collision: CollisionAsset = field(default_factory=CollisionAsset)
    navigation: NavigationAsset = field(default_factory=NavigationAsset)
    capture: Optional[CaptureInfo] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        collision_dict = asdict(self.collision)
        nav_dict = asdict(self.navigation)
        nav_dict = {k: v for k, v in nav_dict.items() if v is not None}
        
        d = {
            "level_version": self.level_version,
            "name": self.name,
            "scale": self.scale,
            "spawn": asdict(self.spawn),
            "render": asdict(self.render),
            "collision": collision_dict,
            "navigation": nav_dict,
        }
        if self.capture:
            capture_dict = asdict(self.capture)
            d["capture"] = {k: v for k, v in capture_dict.items() if v is not None}
        return d

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LevelJson":
        """Create LevelJson from dictionary."""
        spawn_data = d.get("spawn", {})
        spawn = Spawn(**spawn_data)
        
        render_data = d.get("render", {})
        render = RenderAsset(**render_data)
        
        collision_data = d.get("collision", {}).copy()
        player_data = collision_data.pop("player", {})
        player = PlayerCollision(**player_data)
        collision = CollisionAsset(**collision_data, player=player)
        
        nav_data = d.get("navigation", {})
        navigation = NavigationAsset(**nav_data)
        
        capture = None
        if "capture" in d and d["capture"]:
            capture = CaptureInfo(**d["capture"])
        
        return cls(
            level_version=d.get("level_version", 1),
            name=d.get("name", "Level 0"),
            scale=d.get("scale", {"meters_per_unit": 1.0}),
            spawn=spawn,
            render=render,
            collision=collision,
            navigation=navigation,
            capture=capture,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "LevelJson":
        """Create LevelJson from JSON string."""
        return cls.from_dict(json.loads(json_str))


def make_manifest(
    title: str = "Untitled World",
    levels: Optional[List[Level]] = None,
    tags: Optional[List[str]] = None,
    thumbnail: Optional[str] = None,
) -> Manifest:
    """
    Create a new manifest with sensible defaults.
    
    Args:
        title: World title
        levels: List of level references (defaults to single level)
        tags: Optional tags for categorization
        thumbnail: Optional path to thumbnail image
    
    Returns:
        Manifest instance ready for serialization
    """
    if levels is None:
        levels = [Level(id="0", path="levels/0/level.json", name="Floor 0")]
    
    assets = {}
    if thumbnail:
        assets["thumbnail"] = thumbnail
    
    return Manifest(
        levels=levels,
        generator=Generator(),
        world=World(title=title, tags=tags or []),
        assets=assets,
    )


def make_level_json(
    name: str = "Level 0",
    spawn_position: Optional[List[float]] = None,
    player_height: float = 1.7,
    render_uri: str = "render.glb",
    collision_uri: str = "collision.rlevox",
) -> LevelJson:
    """
    Create a new level.json with sensible defaults.
    
    Args:
        name: Level name
        spawn_position: [x, y, z] spawn position in meters
        player_height: Player eye height in meters
        render_uri: Relative path to render asset
        collision_uri: Relative path to collision asset
    
    Returns:
        LevelJson instance ready for serialization
    """
    spawn_pos = spawn_position or [0.0, player_height, 0.0]
    
    return LevelJson(
        name=name,
        spawn=Spawn(position=spawn_pos),
        render=RenderAsset(uri=render_uri),
        collision=CollisionAsset(
            uri=collision_uri,
            player=PlayerCollision(height_m=player_height),
        ),
    )
