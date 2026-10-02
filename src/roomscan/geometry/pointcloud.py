"""Depth -> world point cloud for Stray Scanner / ARKit captures."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import cv2

from ..tiers.lidar import load_stray, scale_intrinsics


def backproject(depth_mm: np.ndarray, conf: np.ndarray | None, K_depth, T_world_cam: np.ndarray,
                min_conf: int = 2, max_range_m: float = 6.0, pixel_stride: int = 2) -> np.ndarray:
    """Stray Scanner poses are camera->world with an OpenCV camera frame (x right, y down, z forward).
    World frame is ARKit: y up (gravity-aligned). Verified empirically: scripts/test_convention.py
    puts a sharp floor peak ~1.4 m below the camera with this convention and none with the ARKit one."""
    fx, fy, cx, cy = K_depth
    h, w = depth_mm.shape
    vs, us = np.mgrid[0:h:pixel_stride, 0:w:pixel_stride]
    d = depth_mm[vs, us].astype(np.float32) / 1000.0
    mask = (d > 0.1) & (d < max_range_m)
    if conf is not None:
        mask &= conf[vs, us] >= min_conf
    u, v, d = us[mask], vs[mask], d[mask]
    x = (u - cx) / fx * d
    y = (v - cy) / fy * d
    z = d
    pc = np.stack([x, y, z, np.ones_like(z)], axis=0)
    return (T_world_cam @ pc)[:3].T


def fuse(capture: Path, stride: int = 6, max_frames: int | None = None, **kw) -> tuple[np.ndarray, np.ndarray]:
    """Return (points Nx3 in ARKit world, camera positions Fx3)."""
    frames = load_stray(capture, stride=stride)
    if max_frames:
        frames = frames[:: max(1, len(frames) // max_frames)]
    pts, cams = [], []
    for T, (fx, fy, cx, cy), dpath, cpath in frames:
        depth = cv2.imread(str(dpath), cv2.IMREAD_UNCHANGED)
        conf = cv2.imread(str(cpath), cv2.IMREAD_UNCHANGED) if cpath else None
        Kd = scale_intrinsics(fx, fy, cx, cy, depth.shape[1], depth.shape[0])
        pts.append(backproject(depth, conf, Kd, T, **kw))
        cams.append(T[:3, 3])
    return np.concatenate(pts), np.array(cams)
