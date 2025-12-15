# .stella File Format Documentation

## Overview

The `.stella` file format is designed to serve as a container for 3D world data, enabling the storage and retrieval of various assets and metadata necessary for rendering and interaction in virtual environments. This format is structured as a ZIP archive containing essential files that define the world, its components, and associated metadata.

## Container Structure

A `.stella` file is organized as follows:

```
/manifest.json
/levels/0/level.json
/levels/0/render.glb
/levels/0/collision.rlevox
```

### Required Files

1. **manifest.json**: This file serves as the primary descriptor for the `.stella` package, detailing the format version, creation date, units of measurement, and paths to level files.

2. **levels/<n>/level.json**: Each level file defines the properties of a specific scene or floor, including spawn points, scale, and references to render and collision files.

3. **levels/<n>/render.glb**: This file contains the visual representation of the level, typically in the GLB format, which is optimized for web and mobile applications.

4. **levels/<n>/collision.rlevox**: This file provides the collision data for the level, using a sparse voxel representation to define solid and empty spaces within the environment.

### Recommended Files

- **thumbs/cover.jpg**: A thumbnail image representing the world, useful for previews in file explorers.
- **levels/<n>/navmesh.bin**: An optional navigation mesh file for AI pathfinding.
- **levels/<n>/semantics.json**: An optional file containing semantic information about rooms and openings within the level.
- **checksums.sha256**: A file containing SHA256 checksums for integrity verification of the package contents.

## File Specifications

### manifest.json

The `manifest.json` file includes the following fields:

- **format**: The format identifier, e.g., "stella.world".
- **version**: The version of the format, e.g., 1.
- **created_utc**: The UTC timestamp of when the file was created.
- **units**: The units of measurement used in the world, typically "meters".
- **axis**: Defines the coordinate system used (up, forward, handedness).
- **levels**: An array of level definitions, each containing an ID and path to the corresponding `level.json`.

### level.json

The `level.json` file contains:

- **level_version**: The version of the level format.
- **name**: The name of the level.
- **scale**: The scale of the level in meters per unit.
- **spawn**: The spawn position and orientation for the player.
- **render**: The type and URI of the render file.
- **collision**: The type and URI of the collision file, along with player dimensions.
- **navigation**: Optional navigation data.

### collision.rlevox

The `collision.rlevox` file is structured as follows:

- **Header**: Contains metadata such as magic number, version, dimensions, voxel size, and origin.
- **Payload**: Encodes the occupancy data using run-length encoding (RLE) for efficient storage.

## Conclusion

The `.stella` file format is designed to be flexible and extensible, allowing for the integration of various assets and metadata necessary for creating immersive 3D environments. By adhering to this structure, developers can ensure compatibility across different platforms and applications.