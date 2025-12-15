# 🎥 Process Your Video → 3D World

## Quick Start: Use Google Colab (Free GPU)

Since MASt3R-SLAM requires an NVIDIA GPU and you're on a Mac, the easiest way is to use Google Colab:

### Instructions:

1. **Upload the notebook to Google Colab:**
   - Go to: https://colab.research.google.com/
   - Click **File → Upload notebook**
   - Upload: `Process_Video_with_MASt3R_SLAM.ipynb`

2. **Enable GPU:**
   - Click **Runtime → Change runtime type**
   - Set **Hardware accelerator** to **GPU** (T4)
   - Click **Save**

3. **Run the notebook:**
   - Click **Runtime → Run all**
   - When prompted, upload your video: `/Users/rossermcintosh/Downloads/2695c46f-770f-4c53-a6a8-ab1ea3961e44.MP4`
   - Wait 15-30 minutes for processing
   - Download the results at the end

4. **What you get:**
   - `apartment_tour.ply` - 3D point cloud (open in MeshLab/Blender)
   - `apartment_tour.stella` - Explorable 3D world (open in VS Code)

---

## Alternative: Use a Cloud GPU Service

If you need more control or faster processing:

### Option 1: Lambda Labs ($1.10/hour for A10 GPU)

```bash
# SSH into Lambda Labs instance
ssh ubuntu@<your-instance-ip>

# Clone and setup
git clone https://github.com/rmurai0610/MASt3R-SLAM.git --recursive
cd MASt3R-SLAM
conda create -n mast3r-slam python=3.11 -y
conda activate mast3r-slam

# Install dependencies
pip install torch torchvision torchaudio
pip install -e thirdparty/mast3r
pip install -e thirdparty/in3d
pip install --no-build-isolation -e .

# Download checkpoints
mkdir -p checkpoints/
wget https://download.europe.naverlabs.com/ComputerVision/MASt3R/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric.pth -P checkpoints/
wget https://download.europe.naverlabs.com/ComputerVision/MASt3R/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric_retrieval_trainingfree.pth -P checkpoints/
wget https://download.europe.naverlabs.com/ComputerVision/MASt3R/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric_retrieval_codebook.pkl -P checkpoints/

# Upload your video (use scp from your Mac)
# scp ~/Downloads/2695c46f-770f-4c53-a6a8-ab1ea3961e44.MP4 ubuntu@<ip>:~/MASt3R-SLAM/

# Run processing
python main.py \
    --dataset apartment.MP4 \
    --save-as apartment_tour \
    --config config/base.yaml \
    --no-viz

# Download results (from your Mac)
# scp ubuntu@<ip>:~/MASt3R-SLAM/logs/apartment_tour/apartment_tour.ply ~/Downloads/
```

### Option 2: RunPod ($0.30-0.80/hour)

1. Go to https://www.runpod.io/
2. Create instance with PyTorch template
3. Follow same commands as Lambda Labs

### Option 3: Vast.ai (Budget - $0.20-0.50/hour)

1. Go to https://vast.ai/
2. Search for "pytorch" instances
3. Follow same setup steps

---

## Local Processing (If you get access to a GPU)

If you have access to a Windows/Linux machine with NVIDIA GPU:

```bash
# Activate conda environment
conda activate mast3r-slam

# Process video
cd "/path/to/MASt3R-SLAM-main 2"
python main.py \
    --dataset "/path/to/video.mp4" \
    --save-as output_name \
    --config config/base.yaml \
    --no-viz

# Create .stella file
cd mast3r-slam-stella
python -c "
from stella.pipeline_video import build_video
build_video(
    input_video='/path/to/video.mp4',
    output_stella='./output.stella',
    voxel_size=0.1,
    title='My World',
    use_existing_ply='/path/to/MASt3R-SLAM-main 2/logs/output_name/output_name.ply'
)
"
```

---

## Troubleshooting

### "No CUDA GPU detected"
- **Solution:** Use Google Colab or a cloud GPU service (Lambda, RunPod, Vast.ai)
- Macs don't have NVIDIA GPUs - you need CUDA for MASt3R-SLAM

### "Out of memory"
- **Solution:** Reduce video length or resolution
- Try processing only first 2-3 minutes of video

### "Model checkpoints not found"
- **Solution:** Run the wget commands to download the model files
- They're about 1.5GB total

---

## What's Next?

Once you have the `.stella` file:

1. **Extract it:**
   ```bash
   stella extract apartment.stella ./extracted/
   ```

2. **View in VS Code:**
   - Install the VS Code extension (from `extensions/vscode-stella/`)
   - Double-click the `.stella` file
   - Use WASD + mouse to explore!

3. **View the PLY:**
   - Open in MeshLab: https://www.meshlab.net
   - Or CloudCompare: https://cloudcompare.org
   - Or Blender: https://blender.org

---

## Summary

**Your apartment video will work perfectly** - you just need to run it on a machine with an NVIDIA GPU. Google Colab is the easiest (and free!) option.

**Timeline:**
- Upload to Colab: 2 minutes
- Video upload: 2-5 minutes (depending on size)
- Processing: 15-30 minutes (automatic)
- Download results: 2 minutes

**Total: ~30 minutes** and you'll have your explorable 3D apartment!
