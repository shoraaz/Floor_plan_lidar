"""LiDAR tier: Stray Scanner export -> PropertyPlan. Highest-accuracy path.

Verified against the real exports in `property project/` :
  rgb.mp4                 1920x1440 colour video, ~60 fps
  depth/NNNNNN.png        uint16 millimetres, 256x192 (ARKit LiDAR depth)
  confidence/NNNNNN.png   0/1/2 per depth pixel
  camera_matrix.csv       3x3 K for the 1920x1440 RGB frame (NOT the depth map)
  odometry.csv            timestamp, frame, x, y, z, qx, qy, qz, qw, fx, fy, cx, cy, ... (per-frame K too)
  imu.csv                 timestamp, a_x..a_z, alpha_x..alpha_z
Poses: camera->world, OpenCV camera frame (x right, y down, z forward); world is ARKit y-up.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R

from ..models import PropertyPlan, Room, Wall, Interval
from .. import calibration

RGB_W, RGB_H = 1920, 1440


def load_stray(p: Path, stride: int = 6):
    """Per-frame (T_world_cam, (fx,fy,cx,cy) at RGB res, depth_path, conf_path), subsampled by `stride`."""
    odo = pd.read_csv(p / "odometry.csv", skipinitialspace=True)
    odo.columns = [c.strip() for c in odo.columns]
    depth_files = sorted((p / "depth").glob("*.png"))
    conf_files = sorted((p / "confidence").glob("*.png"))
    n = min(len(odo), len(depth_files))
    # stride is nominal for Stray's ~60 Hz logging; low-rate inputs (e.g. converted 10 Hz ARKitScenes) are
    # rescaled so every input ends up at ~10 Hz keyframes. 60 Hz Stray data is unaffected.
    if len(odo) > 2:
        rate = (len(odo) - 1) / max(float(odo["timestamp"].iloc[-1] - odo["timestamp"].iloc[0]), 1e-6)
        if rate < 30:
            stride = max(1, int(round(stride * rate / 60)))
    frames = []
    for i in range(0, n, stride):
        row = odo.iloc[i]
        T = np.eye(4)
        T[:3, :3] = R.from_quat([row.qx, row.qy, row.qz, row.qw]).as_matrix()
        T[:3, 3] = [row.x, row.y, row.z]
        frames.append((T, (row.fx, row.fy, row.cx, row.cy), depth_files[i], conf_files[i] if i < len(conf_files) else None))
    return frames


def scale_intrinsics(fx, fy, cx, cy, depth_w: int, depth_h: int):
    sx, sy = depth_w / RGB_W, depth_h / RGB_H
    return fx * sx, fy * sy, cx * sx, cy * sy


def _cache_path(capture: Path, stride: int, drift: bool = False) -> Path:
    tag = f"{capture.resolve()}|{stride}" + ("|drift2" if drift else "")
    h = hashlib.sha1(tag.encode()).hexdigest()[:12]
    d = Path("cache"); d.mkdir(exist_ok=True)
    return d / f"lidar_{h}.npz"


def fused(capture: Path, stride: int = 6, voxel: float = 0.015, drift: bool = False):
    """Fuse depth into a voxelised cloud + camera path + ray endpoints, cached deterministically on disk.
    drift=True applies start-end loop closure (geometry/drift.py); drift=False = raw ARKit poses (ablation)."""
    import json
    import open3d as o3d
    from ..geometry.pointcloud import fuse, fuse_with_drift
    cp = _cache_path(capture, stride, drift)
    if cp.exists():
        z = np.load(cp)
        return z["P"], z["cams"], np.split(z["R"], z["off"])
    if drift:
        pts, cams, rays, info = fuse_with_drift(capture, stride=stride, drift=True)
        cp.with_suffix(".drift.json").write_text(json.dumps(info, indent=1))
    else:
        pts, cams, rays = fuse(capture, stride=stride)
    P = np.asarray(o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts)).voxel_down_sample(voxel).points)
    np.savez_compressed(cp, P=P, cams=cams, R=np.concatenate(rays), off=np.cumsum([len(r) for r in rays])[:-1])
    return P, cams, rays


def drift_info(capture: Path, stride: int = 6) -> dict:
    import json
    p = _cache_path(capture, stride, True).with_suffix(".drift.json")
    return json.loads(p.read_text()) if p.exists() else {}


def run(capture: Path, drift_correction: bool = True) -> PropertyPlan:
    from ..geometry.backend import plan_from_cloud
    P, cams, rays = fused(capture, drift=drift_correction)
    warnings: list[str] = []
    extra = {"drift_correction": drift_correction}
    if drift_correction:
        info = drift_info(capture)
        extra.update({f"drift_{k}": (round(v, 4) if isinstance(v, float) else v) for k, v in info.items()})
        if info.get("loop") != "accepted":
            warnings.append(f"drift: no loop closure applied ({info.get('loop', 'unknown')}); ARKit poses used")
    else:
        warnings.append("drift correction disabled (ablation): raw ARKit poses")
    return plan_from_cloud(P, cams, rays, capture.name, "lidar", warnings, extra)