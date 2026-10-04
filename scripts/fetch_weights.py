"""Pre-fetch every pretrained model the pipeline uses, so a live run never waits on a download.

Both are Apache-2.0 (Depth Anything 3, ByteDance Seed), used by the video and photo tiers only:
  depth-anything/DA3-LARGE-1.1    any-view: camera poses + depth across frames
  depth-anything/DA3METRIC-LARGE  monocular metric depth (metres = output x focal / 300)
The LiDAR tier uses no learned model.

uv run python scripts/fetch_weights.py
"""
from huggingface_hub import snapshot_download

for repo in ("depth-anything/DA3-LARGE-1.1", "depth-anything/DA3METRIC-LARGE"):
    print("fetching", repo, "->", snapshot_download(repo_id=repo))
