"""Pose front end for the video/photo tiers: Depth Anything 3 any-view model (DA3-LARGE-1.1, Apache-2.0)
in overlapping chunks, chained by similarity transforms on the shared frames, scaled to metres with
DA3METRIC-LARGE. Replaces COLMAP SIFT SfM, which registered only 13-21% of keyframes on low-texture walls.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import cv2

ANYVIEW_MODEL = "depth-anything/DA3-LARGE-1.1"
METRIC_MODEL = "depth-anything/DA3METRIC-LARGE"


def _to44(E: np.ndarray) -> np.ndarray:
    if E.shape == (4, 4):
        return E.astype(np.float64)
    M = np.eye(4); M[:3, :4] = E
    return M


def _sim3_from_poses(Twc_src: list[np.ndarray], Twc_dst: list[np.ndarray]):
    """Similarity (s, R, t) with dst = s*R*src + t, from corresponding camera-to-world poses.
    Rotation: chordal mean of R_dst R_src^T; scale: ratio of centre spreads; translation: centroids."""
    Rs = [Td[:3, :3] @ Ts[:3, :3].T for Ts, Td in zip(Twc_src, Twc_dst)]
    U, _, Vt = np.linalg.svd(np.sum(Rs, axis=0))
    R = U @ Vt
    if np.linalg.det(R) < 0:
        U[:, -1] *= -1; R = U @ Vt
    cs = np.array([T[:3, 3] for T in Twc_src]); cd = np.array([T[:3, 3] for T in Twc_dst])
    ms, md = cs.mean(0), cd.mean(0)
    ss = np.linalg.norm(cs - ms, axis=1).sum(); sd = np.linalg.norm(cd - md, axis=1).sum()
    s = sd / ss if ss > 1e-6 else 1.0
    t = md - s * R @ ms
    return s, R, t


def chunked_poses(images: list[np.ndarray], chunk: int = 24, overlap: int = 8, process_res: int = 504,
                  device: str = "cuda"):
    """Returns per-frame (Twc 4x4 in a common frame, depth HxW in that frame's units, K 3x3 at depth res, conf)."""
    import torch
    from depth_anything_3.api import DepthAnything3
    model = DepthAnything3.from_pretrained(ANYVIEW_MODEL).to(device).eval()
    n = len(images)
    starts = list(range(0, max(n - overlap, 1), chunk - overlap))
    Twc_g = [None] * n; depth_g = [None] * n; K_g = [None] * n; conf_g = [None] * n
    for ci, s0 in enumerate(starts):
        idx = list(range(s0, min(s0 + chunk, n)))
        if len(idx) < 2:
            break
        with torch.no_grad():
            pred = model.inference([images[i] for i in idx], process_res=process_res)
        Twc_c = [np.linalg.inv(_to44(E)) for E in pred.extrinsics]       # extrinsics are world->camera
        D = pred.depth.astype(np.float32)
        C = pred.conf.astype(np.float32) if pred.conf is not None else np.ones_like(D)
        if ci == 0:
            s, R, t = 1.0, np.eye(3), np.zeros(3)
        else:
            shared = [k for k, i in enumerate(idx) if Twc_g[i] is not None]
            _, R, _ = _sim3_from_poses([Twc_c[k] for k in shared], [Twc_g[idx[k]] for k in shared])
            # scale from the depth maps of the shared frames (dense, stable), not from camera spread (tiny on a slow walk)
            ratios = []
            for k in shared:
                a, b = depth_g[idx[k]], D[k]
                m = (a > 0) & (b > 0) & (C[k] >= np.percentile(C[k], 30))
                if m.sum() > 500:
                    ratios.append(np.median(a[m] / b[m]))
            s = float(np.median(ratios)) if ratios else 1.0
            cs = np.array([Twc_c[k][:3, 3] for k in shared]); cd = np.array([Twc_g[idx[k]][:3, 3] for k in shared])
            t = cd.mean(0) - s * R @ cs.mean(0)
        for k, i in enumerate(idx):
            if Twc_g[i] is not None:
                continue
            T = Twc_c[k].copy()
            T[:3, :3] = R @ T[:3, :3]
            T[:3, 3] = s * R @ T[:3, 3] + t
            Twc_g[i] = T; depth_g[i] = D[k] * s; K_g[i] = pred.intrinsics[k].astype(np.float64); conf_g[i] = C[k]
        torch.cuda.empty_cache()
    del model
    return Twc_g, depth_g, K_g, conf_g


def metric_scale(images: list[np.ndarray], depth_rel: list[np.ndarray], K: list[np.ndarray], every: int = 3,
                 device: str = "cuda") -> tuple[float, float, list[float]]:
    """Scale (metres per model unit) = median over frames of median(metric depth / chain depth)."""
    import torch
    from depth_anything_3.api import DepthAnything3
    model = DepthAnything3.from_pretrained(METRIC_MODEL).to(device).eval()
    ratios = []
    for i in range(0, len(images), every):
        if depth_rel[i] is None:
            continue
        with torch.no_grad():
            pred = model.inference([images[i]])
        dm = pred.depth[0].astype(np.float32)
        f_proc = K[i][0, 0] * dm.shape[1] / depth_rel[i].shape[1]   # focal from the any-view model, same image
        dm = dm * float(f_proc) / 300.0
        dr = cv2.resize(depth_rel[i], (dm.shape[1], dm.shape[0]), interpolation=cv2.INTER_NEAREST)
        m = (dm > 0.3) & (dm < 6) & (dr > 0)
        if m.sum() > 500:
            ratios.append(float(np.median(dm[m] / dr[m])))
    del model
    torch.cuda.empty_cache()
    r = np.array(ratios)
    s = float(np.median(r))
    return s, float(np.median(np.abs(r / s - 1))), ratios


def fuse_frames(Twc: list, depth: list, K: list, conf: list, scale: float, stride: int = 3, max_range: float = 6.0,
                conf_pct: float = 30.0, ray_samples: int = 400):
    """Backproject chain depth (x scale = metres) with scaled poses. Drops low-confidence and depth-edge pixels."""
    rng = np.random.default_rng(0)
    pts, cams, rays, Twcs = [], [], [], []
    for T, D, Kk, C in zip(Twc, depth, K, conf):
        if T is None:
            continue
        Dm = D * scale
        Tm = T.copy(); Tm[:3, 3] *= scale
        gy, gx = np.gradient(Dm)
        edge = np.hypot(gx, gy) / np.maximum(Dm, 1e-3) > 0.05
        cthr = np.percentile(C, conf_pct)
        vs, us = np.mgrid[0:Dm.shape[0]:stride, 0:Dm.shape[1]:stride]
        d = Dm[vs, us]
        m = (d > 0.2) & (d < max_range) & ~edge[vs, us] & (C[vs, us] >= cthr)
        u, v, d = us[m], vs[m], d[m]
        fx, fy, cx, cy = Kk[0, 0], Kk[1, 1], Kk[0, 2], Kk[1, 2]
        pc = np.stack([(u - cx) / fx * d, (v - cy) / fy * d, d, np.ones_like(d)])
        w = (Tm @ pc)[:3].T
        pts.append(w); cams.append(Tm[:3, 3]); Twcs.append(Tm)
        rays.append(w[rng.choice(len(w), min(ray_samples, len(w)), replace=False)] if len(w) else w)
    return np.concatenate(pts), np.array(cams), rays, Twcs



def chunked_poses_metric(images: list[np.ndarray], chunk: int = 24, overlap: int = 8, process_res: int = 504,
                         metric_every: int = 4, device: str = "cuda"):
    """Like chunked_poses, but each chunk is scaled to metres INDEPENDENTLY (DA3METRIC on its own frames) and
    chunks are chained with a RIGID transform only. Chaining relative scale multiplied per-chunk errors along
    the walk (scale off by 86% after ~54 m on the sample captures); per-chunk metric anchoring keeps each
    chunk's scale error independent (~5-7%) instead of compounding.

    Returns Twc (metres), depth (metres), K, conf, per-chunk scales, relative MAD of per-chunk scale votes.
    """
    import torch
    from depth_anything_3.api import DepthAnything3
    n = len(images)
    starts = list(range(0, max(n - overlap, 1), chunk - overlap))
    model = DepthAnything3.from_pretrained(ANYVIEW_MODEL).to(device).eval()
    raw = []
    for s0 in starts:
        idx = list(range(s0, min(s0 + chunk, n)))
        if len(idx) < 2:
            break
        with torch.no_grad():
            pred = model.inference([images[i] for i in idx], process_res=process_res)
        raw.append((idx, [np.linalg.inv(_to44(E)) for E in pred.extrinsics], pred.depth.astype(np.float32),
                    pred.conf.astype(np.float32) if pred.conf is not None else np.ones_like(pred.depth, np.float32),
                    [k.astype(np.float64) for k in pred.intrinsics]))
        torch.cuda.empty_cache()
    del model; torch.cuda.empty_cache()

    mmodel = DepthAnything3.from_pretrained(METRIC_MODEL).to(device).eval()
    scales, votes_mad = [], []
    for idx, Tc, D, C, K in raw:
        ratios = []
        for k in range(0, len(idx), metric_every):
            with torch.no_grad():
                pm = mmodel.inference([images[idx[k]]])
            dm = pm.depth[0].astype(np.float32)
            dm = dm * float(K[k][0, 0] * dm.shape[1] / D[k].shape[1]) / 300.0
            dr = cv2.resize(D[k], (dm.shape[1], dm.shape[0]), interpolation=cv2.INTER_NEAREST)
            m = (dm > 0.3) & (dm < 6) & (dr > 0)
            if m.sum() > 500:
                ratios.append(float(np.median(dm[m] / dr[m])))
        s = float(np.median(ratios)) if ratios else (scales[-1] if scales else 1.0)
        scales.append(s)
        if ratios:
            votes_mad.append(float(np.median(np.abs(np.array(ratios) / s - 1))))
    del mmodel; torch.cuda.empty_cache()

    Twc_g = [None] * n; depth_g = [None] * n; K_g = [None] * n; conf_g = [None] * n
    for ci, ((idx, Tc, D, C, K), s) in enumerate(zip(raw, scales)):
        Tm = []
        for T in Tc:
            T2 = T.copy(); T2[:3, 3] *= s; Tm.append(T2)
        if ci == 0:
            R, t = np.eye(3), np.zeros(3)
        else:
            shared = [k for k, i in enumerate(idx) if Twc_g[i] is not None]
            _, R, _ = _sim3_from_poses([Tm[k] for k in shared], [Twc_g[idx[k]] for k in shared])
            cs = np.array([Tm[k][:3, 3] for k in shared]); cd = np.array([Twc_g[idx[k]][:3, 3] for k in shared])
            t = cd.mean(0) - R @ cs.mean(0)
        for k, i in enumerate(idx):
            if Twc_g[i] is not None:
                continue
            T = Tm[k].copy()
            T[:3, :3] = R @ T[:3, :3]; T[:3, 3] = R @ T[:3, 3] + t
            Twc_g[i] = T; depth_g[i] = D[k] * s; K_g[i] = K[k]; conf_g[i] = C[k]
    spread = float(np.median(np.abs(np.array(scales) / np.median(scales) - 1))) if scales else 1.0
    return Twc_g, depth_g, K_g, conf_g, scales, spread
