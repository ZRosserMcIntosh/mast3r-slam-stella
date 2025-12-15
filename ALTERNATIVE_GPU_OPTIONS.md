# Alternative Ways to Run MASt3R-SLAM (Without Local NVIDIA GPU)

MASt3R-SLAM requires NVIDIA CUDA at multiple levels:
1. **lietorch** - Lie group library (explicitly blocks macOS)
2. **mast3r_slam_backends** - Custom CUDA kernels
3. **MASt3R model** - Neural network (needs GPU for reasonable speed)

## Why It Won't Run on Mac (Intel i9)
- lietorch has `raise NotImplementedError("Error: Darwin is not a supported platform")`
- Custom CUDA kernels (.cu files) require nvcc compiler
- Even with workarounds, processing would be impractically slow

---

## Option 1: RunPod (Recommended - Cheapest & Easiest)

[RunPod](https://runpod.io) is a GPU cloud service with pre-configured PyTorch environments.

### Setup (~10 minutes):
1. Create account at https://runpod.io
2. Add $10-20 credit (pay-as-you-go)
3. Deploy a **Secure Cloud** pod:
   - Template: `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`
   - GPU: RTX 3090 (~$0.44/hr) or RTX 4090 (~$0.74/hr)
   - Disk: 50GB
4. Connect via JupyterLab or SSH

### Commands to run:
```bash
# Clone MASt3R-SLAM
git clone --recursive https://github.com/rmurai0610/MASt3R-SLAM.git
cd MASt3R-SLAM

# Install dependencies (lietorch works here!)
pip install lietorch roma pyglet einops trimesh scipy plyfile opencv-python
cd thirdparty/mast3r/dust3r/croco/models/curope && pip install . && cd -
pip install -e thirdparty/mast3r/asmk
pip install --no-deps -e thirdparty/mast3r
pip install glfw pyglm moderngl moderngl-window
pip install --no-deps -e thirdparty/in3d
pip install --no-deps -e .

# Download checkpoints
mkdir -p checkpoints
wget -P checkpoints/ https://download.europe.naverlabs.com/ComputerVision/MASt3R/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric.pth
wget -P checkpoints/ https://download.europe.naverlabs.com/ComputerVision/MASt3R/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric_retrieval_trainingfree.pth
wget -P checkpoints/ https://download.europe.naverlabs.com/ComputerVision/MASt3R/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric_retrieval_codebook.pkl

# Upload your video and run
python main.py --dataset your_video.mp4 --save-as output --config config/base.yaml --no-viz
```

**Cost estimate:** ~$2-5 for a 30-minute video

---

## Option 2: Lambda Labs

[Lambda Labs](https://lambdalabs.com/service/gpu-cloud) offers GPU instances with PyTorch pre-installed.

### Pricing:
- A10 GPU: $0.75/hr
- RTX 6000: $0.50/hr

Same setup commands as RunPod.

---

## Option 3: Vast.ai (Cheapest)

[Vast.ai](https://vast.ai) is a marketplace for cheap GPU rentals.

### How to use:
1. Create account at https://vast.ai
2. Rent an RTX 3090 instance (~$0.20-0.40/hr)
3. Use their Docker template with PyTorch + CUDA

---

## Option 4: Google Colab Pro+ with High-RAM A100

Colab's Python 3.12 environment has lietorch compatibility issues. 
**Colab Pro+ with A100** might work better because it uses a different base image.

Try:
1. Subscribe to Colab Pro+ ($49/month)
2. Select "A100 GPU" runtime
3. Run the notebook

---

## Option 5: Use Pre-Computed Results

If you just want to test the `.stella` viewer, you can:
1. Use a sample `.stella` file (we can provide one)
2. Download pre-computed 3D reconstructions from datasets like Replica/ScanNet
3. Convert them to `.stella` format

---

## Recommended Path

1. **First try:** RunPod (10 min setup, ~$2-5 total cost)
2. **Backup:** Lambda Labs or Vast.ai
3. **If budget limited:** Try Colab Pro+ A100

---

## Quick Cost Comparison

| Service | GPU | Price/hr | Est. Total |
|---------|-----|----------|------------|
| RunPod | RTX 3090 | $0.44 | ~$2-3 |
| RunPod | RTX 4090 | $0.74 | ~$3-5 |
| Vast.ai | RTX 3090 | ~$0.25 | ~$1-2 |
| Lambda | A10 | $0.75 | ~$3-5 |
| Colab Pro | T4/V100 | $9.99/mo | Subscription |
| Colab Pro+ | A100 | $49.99/mo | Subscription |

For a one-time video processing job, RunPod or Vast.ai is most cost-effective.
