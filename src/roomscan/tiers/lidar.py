"""LiDAR tier: Stray Scanner export -> RoomGeometry. Highest-accuracy path.

Verified against the real exports in `property project/` :
  rgb.mp4                 1920x1440 colour video, ~60 fps
  depth/NNNNNN.png        uint16 millimetres, 256x192 (ARKit LiDAR depth)
  confidence/NNNNNN.png   0/1/2 per depth pixel
  camera_matrix.csv       3x3 K for the 1920x1440 RGB frame (NOT the depth map)
  odometry.csv            timestamp, frame, x, y, z, qx, qy, qz, qw, fx, fy, cx, cy, ... (per-frame K too)
  imu.csv                 timestamp, a_x..a_z, alpha_x..alpha_z
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R

from ..models import PropertyPlan

RGB_W, RGB_H = 1920, 1440


def load_stray(p: Path, stride: int = 6):
    """Return per-frame (T_world_cam, K_depth, depth_path, conf_path) subsampled by `stride`.

    Intrinsics are rescaled from RGB resolution to the depth map resolution.
    ARKit camera axes: x right, y up, z backward (camera looks down -z).
    """
    odo = pd.read_csv(p / "odometry.csv", skipinitialspace=True)
    odo.columns = [c.strip() for c in odo.columns]
    depth_files = sorted((p / "depth").glob("*.png"))
    conf_files = sorted((p / "confidence").glob("*.png"))
    n = min(len(odo), len(depth_files))
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


def run(capture: Path, drift_correction: bool = True) -> PropertyPlan:
    frames = load_stray(capture)
    # TODO(step 2): backproject depth (conf>=2) -> world cloud; verify axis convention on real data;
    #   floor/ceiling RANSAC; Manhattan wall planes; room polygon; openings; ceiling height + interval.
    # TODO(step 3): if drift_correction: pose graph + plane-anchored constraints (geometry/drift.py).
    raise NotImplementedError("LiDAR tier not implemented yet")
