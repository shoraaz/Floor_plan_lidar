"""Photo tier: a folder of per-room photo folders (2-8 stills each, any phone, no depth/poses) -> stitched plan.

Front end:
  1. load every photo, resize to 960 px wide, remember its room folder
  2. ONE joint Depth Anything 3 any-view pass over all photos (DA3-LARGE-1.1, Apache-2.0): poses + depth in a
     single frame for the whole property. Rooms are stitched by the model's cross-view matching, which works when
     each room's folder contains a photo of the doorway it shares with its neighbour (capture protocol rule).
     If the set is larger than one pass can hold, it falls back to overlapping chunks (stitching then relies on
     chunk overlaps across folders and is flagged).
  3. metric scale from DA3METRIC-LARGE (median ratio over all photos)
  4. fuse -> gravity align -> shared geometry backend (same as LiDAR/video), with widened intervals
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import cv2

from ..models import PropertyPlan

IMG_EXT = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
MAX_JOINT = 40          # photos per single DA3 pass on an 8 GB GPU at 504 px


def _load(folder: Path, width: int = 960):
    rooms = sorted(d for d in folder.iterdir() if d.is_dir())
    imgs, owner, names = [], [], []
    for d in rooms:
        for p in sorted(x for x in d.iterdir() if x.suffix.lower() in IMG_EXT):
            if p.suffix.lower() == ".heic":
                from pillow_heif import register_heif_opener
                from PIL import Image
                register_heif_opener()
                rgb = np.array(Image.open(p).convert("RGB"))
            else:
                bgr = cv2.imread(str(p))
                if bgr is None:
                    continue
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            rgb = cv2.resize(rgb, (width, int(round(h * width / w))), interpolation=cv2.INTER_AREA)
            imgs.append(rgb); owner.append(d.name); names.append(p.name)
    return imgs, owner, names, [d.name for d in rooms]


def run(capture: Path, drift_correction: bool = True) -> PropertyPlan:
    from ..geometry.da3_frontend import chunked_poses, metric_scale, fuse_frames
    from ..geometry.backend import plan_from_cloud
    from .video import gravity_align
    import open3d as o3d

    imgs, owner, names, room_dirs = _load(capture)
    warnings = []
    counts = {r: owner.count(r) for r in room_dirs}
    for r, c in counts.items():
        if c < 2:
            warnings.append(f"folder {r}: {c} photo(s); at least 2 needed, room may be missing")
    joint = len(imgs) <= MAX_JOINT
    if joint:
        Twc, D, K, C = chunked_poses(imgs, chunk=len(imgs), overlap=0)
    else:
        warnings.append(f"{len(imgs)} photos exceed one joint pass ({MAX_JOINT}); chunked, cross-room stitching less reliable")
        Twc, D, K, C = chunked_poses(imgs)
    scale, spread, _ = metric_scale(imgs, D, K, every=1)
    P, cams, rays, Twcs = fuse_frames(Twc, D, K, C, scale)
    P = np.asarray(o3d.geometry.PointCloud(o3d.utility.Vector3dVector(P)).voxel_down_sample(0.015).points)
    R = gravity_align(P, cams, np.array([-T[:3, 1] for T in Twcs]))
    P, cams = P @ R.T, cams @ R.T
    rays = [r @ R.T for r in rays]
    warnings.append("photo tier: single-view metric scale + learned multi-view poses; intervals widened accordingly")
    # photo tier has the thinnest evidence: base quality 0.5, reduced further by scale disagreement
    q = float(np.clip(0.5 * (1 - 3 * spread), 0.15, 0.5))
    quality = {"photos": len(imgs), "room_folders": counts, "joint_pass": joint, "metric_scale": round(scale, 5),
               "scale_vote_rel_mad": round(spread, 4)}
    plan = plan_from_cloud(P, cams, rays, capture.name, "photo", warnings, quality, quality_scale=q)
    return plan
