#!/bin/bash
# process_video.sh - Process a video through MASt3R-SLAM and create a .stella world
#
# Usage: ./process_video.sh <input_video.mp4> [output_name]
#
# Example:
#   ./process_video.sh ~/Downloads/apartment_tour.mp4 apartment
#
# This will create:
#   - logs/<output_name>/<output_name>.ply  (3D point cloud)
#   - output/<output_name>.stella            (.stella explorable world)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAST3R_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
STELLA_ROOT="$SCRIPT_DIR/.."

INPUT_VIDEO="$1"
OUTPUT_NAME="${2:-$(basename "$INPUT_VIDEO" .mp4)}"
OUTPUT_NAME="${OUTPUT_NAME%.*}"  # Remove any extension

if [ -z "$INPUT_VIDEO" ]; then
    echo "Usage: $0 <input_video.mp4> [output_name]"
    echo ""
    echo "Example:"
    echo "  $0 ~/Downloads/apartment_tour.mp4 apartment"
    exit 1
fi

if [ ! -f "$INPUT_VIDEO" ]; then
    echo "Error: Video file not found: $INPUT_VIDEO"
    exit 1
fi

echo "=============================================="
echo "MASt3R-SLAM + Stella Pipeline"
echo "=============================================="
echo "Input video:  $INPUT_VIDEO"
echo "Output name:  $OUTPUT_NAME"
echo "MASt3R root:  $MAST3R_ROOT"
echo ""

# Check if conda environment exists
if command -v conda &> /dev/null; then
    echo "Activating mast3r-slam conda environment..."
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate mast3r-slam 2>/dev/null || {
        echo "Warning: Could not activate mast3r-slam environment"
        echo "Make sure you've created it with: conda create -n mast3r-slam python=3.11"
    }
fi

# Create output directory
mkdir -p "$MAST3R_ROOT/output"

# Step 1: Run MASt3R-SLAM
echo ""
echo "Step 1: Running MASt3R-SLAM reconstruction..."
echo "=============================================="
cd "$MAST3R_ROOT"
python main.py \
    --dataset "$INPUT_VIDEO" \
    --save-as "$OUTPUT_NAME" \
    --config config/base.yaml \
    --no-viz

# Find the PLY file
PLY_FILE="$MAST3R_ROOT/logs/$OUTPUT_NAME/$OUTPUT_NAME.ply"
if [ ! -f "$PLY_FILE" ]; then
    echo "Error: PLY file not found at $PLY_FILE"
    echo "Looking for PLY files..."
    find "$MAST3R_ROOT/logs" -name "*.ply" -type f 2>/dev/null
    exit 1
fi

echo ""
echo "PLY reconstruction saved to: $PLY_FILE"

# Step 2: Create .stella world
echo ""
echo "Step 2: Creating .stella world..."
echo "=============================================="

# Install stella package if needed
cd "$STELLA_ROOT"
pip install -e . -q 2>/dev/null || pip install -e . 

STELLA_OUTPUT="$MAST3R_ROOT/output/${OUTPUT_NAME}.stella"

python -c "
from stella.pipeline_video import build_video

build_video(
    input_video='$INPUT_VIDEO',
    output_stella='$STELLA_OUTPUT',
    voxel_size=0.1,
    title='$OUTPUT_NAME',
    use_existing_ply='$PLY_FILE'
)
"

echo ""
echo "=============================================="
echo "DONE!"
echo "=============================================="
echo ""
echo "Outputs:"
echo "  3D Point Cloud:    $PLY_FILE"
echo "  Stella World:      $STELLA_OUTPUT"
echo ""
echo "To view the PLY file:"
echo "  - Open in MeshLab, CloudCompare, or Blender"
echo ""
echo "To view the .stella file:"
echo "  - Install the VS Code extension and double-click the file"
echo "  - Or extract with: stella extract '$STELLA_OUTPUT' ./extracted/"
echo ""
