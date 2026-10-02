"""Fetch pretrained weights / large binaries (not committed to git). Disclosed in the report.

Models (all free):
  - Depth Pro (Apple)      metric monocular depth, photo + video tiers
  - SAM 2 (Meta)           damage / opening segmentation
  - CLIP ViT-B/32          zero-shot damage classification
  - (optional) VGGT / MASt3R   learned pose + geometry for video tier
"""
from pathlib import Path
from huggingface_hub import snapshot_download  # pip install huggingface_hub

W = Path("weights"); W.mkdir(exist_ok=True)
MODELS = {
    "depth_pro": "apple/DepthPro",
    "clip": "openai/clip-vit-base-patch32",
    "sam2": "facebook/sam2-hiera-small",
}

if __name__ == "__main__":
    for name, repo in MODELS.items():
        print(f"fetching {name} <- {repo}")
        snapshot_download(repo_id=repo, local_dir=W / name)
    print("done")
