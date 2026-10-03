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


def fuse(capture: Path, stride: int = 6, max_frames: int | None = None, ray_samples: int = 400, **kw):
    """Return (points Nx3 world, camera positions Fx3, per-frame ray endpoints list[Kx3]).

    Ray endpoints are a random subsample of each frame's points; free space = segments camera->endpoint.
    """
    frames = load_stray(capture, stride=stride)
    if max_frames:
        frames = frames[:: max(1, len(frames) // max_frames)]
    rng = np.random.default_rng(0)
    pts, cams, rays = [], [], []
    for T, (fx, fy, cx, cy), dpath, cpath in frames:
        depth = cv2.imread(str(dpath), cv2.IMREAD_UNCHANGED)
        conf = cv2.imread(str(cpath), cv2.IMREAD_UNCHANGED) if cpath else None
        Kd = scale_intrinsics(fx, fy, cx, cy, depth.shape[1], depth.shape[0])
        w = backproject(depth, conf, Kd, T, **kw)
        pts.append(w)
        cams.append(T[:3, 3])
        rays.append(w[rng.choice(len(w), min(ray_samples, len(w)), replace=False)] if len(w) else w)
    return np.concatenate(pts), np.array(cams), rays


def fuse_frames_list(frames, ray_samples: int = 400, **kw):
    """Fuse an explicit list of (T, K, depth_path, conf_path) frames (e.g. drift-corrected)."""
    rng = np.random.default_rng(0)
    pts, cams, rays = [], [], []
    for T, (fx, fy, cx, cy), dpath, cpath in frames:
        depth = cv2.imread(str(dpath), cv2.IMREAD_UNCHANGED)
        conf = cv2.imread(str(cpath), cv2.IMREAD_UNCHANGED) if cpath else None
        Kd = scale_intrinsics(fx, fy, cx, cy, depth.shape[1], depth.shape[0])
        w = backproject(depth, conf, Kd, T, **kw)
        pts.append(w); cams.append(T[:3, 3])
        rays.append(w[rng.choice(len(w), min(ray_samples, len(w)), replace=False)] if len(w) else w)
    return np.concatenate(pts), np.array(cams), rays


def fuse_with_drift(capture: Path, stride: int = 6, drift: bool = True, **kw):
    """Returns (points, cams, rays, drift_info). drift=False is the ablation baseline (raw ARKit poses)."""
    from .drift import pose_graph_correct
    frames = load_stray(capture, stride=stride)
    info = {"enabled": drift, "method": "pose graph: ARKit odometry edges + ICP-verified revisit loops"}
    if drift:
        new, li = pose_graph_correct(frames)
        info.update(li)
        if new is not None:
            frames = new
    P, C, Rr = fuse_frames_list(frames, **kw)
    return P, C, Rr, info
