# mast3r-slam-stella

MASt3R-SLAM Stella is a project designed to create and manage `.stella` world files, which are ZIP containers that store 3D environments for exploration and interaction. This project integrates with the MASt3R-SLAM system to generate 3D worlds from both floorplan images and video inputs.

## Features

- **Floorplan to 3D World**: Convert 2D floorplan images into 3D environments with collision detection.
- **Video to 3D Scan**: Utilize video input to create point clouds and camera poses, generating explorable 3D worlds.
- **Custom VS Code Extension**: A dedicated extension for viewing and interacting with `.stella` files in a 3D space.

## Project Structure

- **stella/**: Contains the core functionality for creating and managing `.stella` files.
  - `__init__.py`: Initializes the stella package.
  - `manifest.py`: Handles the creation and validation of the manifest.json structure.
  - `package.py`: Provides functions for packing and unpacking `.stella` files.
  - `vox_rle.py`: Implements reading and writing for the collision.rlevox format.
  - `pipeline_floorplan.py`: CLI for building `.stella` files from floorplan images.
  - `pipeline_video.py`: Connects to MASt3R-SLAM for video processing.
  - `geometry.py`: Contains geometric utilities.
  - `cli.py`: Command-line interface functionality.

- **extensions/**: Contains the VS Code extension files.
  - `vscode-stella/`: The folder for the VS Code extension, including configuration and source files.

- **docs/**: Documentation files detailing the `.stella` format and implementation plans.

- **examples/**: Sample files for testing and demonstration purposes.

- **schemas/**: JSON schemas for validating the structure of manifest and level files.

- **tests/**: Unit tests for various modules to ensure functionality and correctness.

## Installation

To install the required dependencies, run:

```
pip install -r requirements.txt
```

## Usage

### Building a World from a Floorplan

To create a `.stella` file from a floorplan image, use the following command:

```
stella build-floorplan --input plan.png --output out.stella --wall-height 2.7 --voxel 0.1 --pixels-per-meter 50
```

### Building a World from Video

To create a `.stella` file from a video, use:

```
stella build-video --input scan.mp4 --output out.stella --voxel 0.1 --max-frames 1500
```

### Opening a `.stella` File

Double-click a `.stella` file in VS Code to open the custom 3D explorer, where you can navigate the environment using WASD controls.

## License

This project is licensed under the CC BY-NC-SA license. Please refer to the LICENSE.md file for more details.