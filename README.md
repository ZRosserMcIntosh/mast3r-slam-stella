# 🌍 MASt3R-SLAM Stella

**Convert videos into explorable 3D worlds with collision detection and first-person controls.**

[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-37%20passing-brightgreen.svg)]()

Process videos or floorplan images into `.stella` files - ZIP containers with 3D meshes, voxel collision, and exploration metadata. Use WASD + mouse controls to walk through reconstructed spaces.

---

## 🚀 Quick Start

### Option 1: Google Colab (FREE GPU - Recommended for Mac users)

1. **Open the notebook:** [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ZRosserMcIntosh/mast3r-slam-stella/blob/main/Process_Video_with_MASt3R_SLAM.ipynb)

2. **Enable GPU:** Runtime → Change runtime type → GPU → Save

3. **Run all cells:** Runtime → Run all

4. **Upload your video** when prompted

5. **Download:** `your_video.ply` (point cloud) + `your_video.stella` (explorable world)

**Time:** ~30 minutes | **Cost:** Free

---

### Option 2: Local Installation (Requires NVIDIA GPU)

```bash
# Clone repository
git clone https://github.com/ZRosserMcIntosh/mast3r-slam-stella.git
cd mast3r-slam-stella

# Install package
pip install -e .

# Process video (requires MASt3R-SLAM with NVIDIA GPU)
stella build-video \
    --input video.mp4 \
    --output world.stella \
    --voxel 0.1

# Or use existing point cloud
stella build-video \
    --input video.mp4 \
    --output world.stella \
    --use-ply existing.ply
```

---

## 📦 What is a `.stella` File?

A `.stella` file is a **ZIP container** (like `.docx`) containing:

```
world.stella (ZIP)
├── manifest.json              # World metadata
└── levels/0/
    ├── level.json             # Spawn point, configuration
    ├── render.glb             # 3D mesh (glTF 2.0 binary)
    └── collision.rlevox       # Voxel collision (RLE compressed)
```

### File Formats

**RLEVOX** - Binary voxel collision:
- 64-byte header (magic "STVX", dimensions, voxel size, origin)
- Run-length encoded (RLE) payload along X axis
- Efficient storage for sparse voxel grids (~10x compression)

**GLB** - 3D render mesh:
- Binary glTF 2.0 format
- Vertex colors from point cloud
- Compatible with Three.js, Babylon.js, Unity, Unreal

**Coordinates:**
- Y-up, -Z forward, right-handed
- Units in meters

---

## 🎮 Features

- **Video → 3D World**: Process MP4/MOV videos with MASt3R-SLAM
- **Floorplan → 3D World**: Convert 2D floorplans to walkable spaces
- **Collision Detection**: Real-time voxel-based collision
- **First-Person Exploration**: WASD + mouse controls
- **VS Code Extension**: Custom 3D viewer with WebGL
- **CLI Tools**: Extract, validate, inspect .stella files

---

## 📚 Documentation

- **[START_HERE.txt](START_HERE.txt)** - Quick start guide
- **[PROCESSING_VIDEO_INSTRUCTIONS.md](PROCESSING_VIDEO_INSTRUCTIONS.md)** - Detailed video processing
- **[README_PROCESSING_VIDEO.md](README_PROCESSING_VIDEO.md)** - Complete overview
- **[STELLA_FORMAT.md](docs/STELLA_FORMAT.md)** - File format specification
- **[FINAL_STATUS.md](FINAL_STATUS.md)** - Implementation details

---

## 🛠️ CLI Usage

```bash
# Build from video
stella build-video --input scan.mp4 --output world.stella

# Build from floorplan
stella build-floorplan --input plan.png --output world.stella --wall-height 2.7

# Inspect .stella file
stella info world.stella
stella validate world.stella

# Extract contents
stella extract world.stella ./output/
```

---

## 🧪 Testing

```bash
# Run tests
pytest tests/

# Results: 37 passed, 1 skipped
```

---

## 🔧 Python API

```python
from stella.pipeline_video import build_video
from stella.package import pack_stella, unpack_stella
from stella.vox_rle import write_rlevox, read_rlevox

# Create .stella from video
build_video(
    input_video="apartment.mp4",
    output_stella="world.stella",
    voxel_size=0.1,
    title="My Apartment"
)

# Extract .stella
manifest, files = unpack_stella("world.stella")

# Read collision data
grid, voxel_size, origin = read_rlevox("collision.rlevox")
```

---

## 🎨 VS Code Extension

Custom editor for `.stella` files with:
- Three.js WebGL 3D viewer
- WASD + mouse look controls (Pointer Lock)
- Real-time collision detection
- FPS counter, position display, crosshair

**Install:**
```bash
cd extensions/vscode-stella
npm install
code --install-extension .
```

**Usage:** Double-click any `.stella` file in VS Code

---

## 📋 Requirements

**Python:**
- Python 3.8+
- numpy >= 1.20.0
- opencv-python >= 4.5.0
- trimesh >= 3.10.0
- scipy >= 1.7.0 (optional)
- open3d >= 0.15.0 (optional)

**For SLAM (video processing):**
- NVIDIA GPU with CUDA
- MASt3R-SLAM ([repository](https://github.com/rmurai0610/MASt3R-SLAM))
- PyTorch with CUDA support

**For Mac users:** Use Google Colab (free GPU in cloud)

---

## 🏗️ Project Structure

```
mast3r-slam-stella/
├── stella/                    # Python package
│   ├── manifest.py           # Dataclasses for JSON schemas
│   ├── package.py            # ZIP pack/unpack
│   ├── vox_rle.py            # RLEVOX format
│   ├── geometry.py           # 3D utilities
│   ├── pipeline_video.py    # Video → .stella
│   ├── pipeline_floorplan.py # Image → .stella
│   └── cli.py                # Command-line interface
├── tests/                     # Unit tests (pytest)
├── extensions/vscode-stella/  # VS Code extension
├── docs/                      # Documentation
├── schemas/                   # JSON schemas
└── Process_Video_with_MASt3R_SLAM.ipynb  # Colab notebook
```

---

## 🤝 Contributing

Contributions welcome! This project is open-source under CC BY-NC-SA 4.0.

**Areas for contribution:**
- Improved mesh reconstruction algorithms
- Better collision voxelization
- Web-based .stella viewer
- Additional file format exporters
- Performance optimizations

---

## 📄 License

This project is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**.

- ✅ Share and adapt for non-commercial use
- ✅ Must give appropriate credit
- ✅ Must share under same license
- ❌ No commercial use without permission

MASt3R-SLAM components: CC BY-NC-SA 4.0 (see [MASt3R-SLAM LICENSE](https://github.com/rmurai0610/MASt3R-SLAM))

---

## 🙏 Acknowledgments

- **MASt3R-SLAM** by Riku Murai & Eric Dexheimer - Visual SLAM system
- **MASt3R** by NAVER LABS Europe - 3D reconstruction model
- **DUSt3R** by NAVER LABS Europe - Depth estimation
- **Three.js** - WebGL 3D library for VS Code viewer

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/ZRosserMcIntosh/mast3r-slam-stella/issues)
- **Documentation:** See `docs/` folder
- **Examples:** See `examples/` folder

---

## 🎯 Use Cases

- **Architecture:** Walkthrough building scans
- **Real Estate:** Virtual property tours
- **Gaming:** Convert real spaces to game levels
- **VR/AR:** Training simulations with real geometry
- **Digital Twins:** Explorable facility documentation
- **Education:** Interactive 3D learning environments

---

**Made with ❤️ for the 3D reconstruction community**
