"""Video tier: handheld walkthrough clip -> PropertyPlan. No depth, no poses, no intrinsics from the phone.

Front end (then the shared geometry backend):
  1. keyframes at `fps` from the clip, resized to `width` px
  2. camera poses + focal length: COLMAP incremental SfM (pycolmap, sequential matching + loop detection)
     -> poses up to an unknown scale
  3. metric depth per keyframe: Depth Anything 3 Metric-Large (Apache-2.0); metres = output * f_proc / 300
     (unit convention verified against LiDAR on the same frames: benchmark/results/da3_vs_lidar_*.log)
  4. metric scale for the SfM model: median over all SfM observations of (DA3 metric depth / SfM depth)
  5. dense cloud: backproject DA3 depth with scaled SfM poses (depth-edge pixels dropped)
  6. gravity: up = mean camera "up" (phone held upright), refined to the floor-plane normal; rotate to y-up
Everything is cached under cache/ keyed by the clip path, so reruns are deterministic.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np
import cv2

from ..models import PropertyPlan

DA3_MODEL = "depth-anything/DA3METRIC-LARGE"


def _clip_path(capture: Path) -> Path:
    if capture.is_dir():          # allow a Stray Scanner folder: use only its rgb.mp4 (video tier ignores the rest)
        return capture / "rgb.mp4"
    return capture


def _cache_dir(clip: Path, fps: float, width: int) -> Path:
    h = hashlib.sha1(f"{clip.resolve()}|{fps}|{width}".encode()).hexdigest()[:12]
    d = Path("cache") / f"video_{h}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def extract_keyframes(clip: Path, out: Path, fps: float = 2.0, width: int = 960, max_frames: int = 400):
    img_dir = out / "images"
    if img_dir.exists() and any(img_dir.iterdir()):
        return sorted(img_dir.glob("*.jpg"))
    img_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(clip))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(round(src_fps / fps)))
    idx = list(range(0, n, step))
    if len(idx) > max_frames:
        idx = list(np.linspace(0, n - 1, max_frames).astype(int))
    paths = []
    for k, i in enumerate(idx):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, bgr = cap.read()
        if not ok:
            continue
        # skip motion-blurred frames: low Laplacian variance
        h, w = bgr.shape[:2]
        bgr = cv2.resize(bgr, (width, int(round(h * width / w))), interpolation=cv2.INTER_AREA)
        p = img_dir / f"{k:05d}.jpg"
        cv2.imwrite(str(p), bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
        paths.append(p)
    return paths


def run_sfm(out: Path):
    import pycolmap
    rec_dir = out / "sparse"
    if (rec_dir / "0" / "images.bin").exists():
        return pycolmap.Reconstruction(str(rec_dir / "0"))
    db = out / "db.db"
    if db.exists():
        db.unlink()
    ext = pycolmap.FeatureExtractionOptions()
    ext.sift.max_num_features = 8192
    ext.sift.peak_threshold = 0.004          # lower than default: indoor walls are low-texture
    pycolmap.extract_features(db, out / "images", camera_mode=pycolmap.CameraMode.SINGLE, extraction_options=ext)
    pairing = pycolmap.SequentialPairingOptions()
    pairing.overlap = 20
    pairing.quadratic_overlap = True
    pycolmap.match_sequential(db, pairing_options=pairing)
    rec_dir.mkdir(exist_ok=True)
    opts = pycolmap.IncrementalPipelineOptions()
    opts.min_model_size = 5
    opts.mapper.init_min_tri_angle = 4.0     # default 16 deg is too strict for a slow walk
    opts.mapper.abs_pose_min_num_inliers = 15
    recs = pycolmap.incremental_mapping(db, out / "images", rec_dir, options=opts)
    if not recs:
        raise RuntimeError("SfM failed: no reconstruction")
    best = max(recs.values(), key=lambda r: r.num_reg_images())
    (rec_dir / "0").mkdir(exist_ok=True)
    best.write(str(rec_dir / "0"))
    return best


def metric_depths(out: Path, rec, names: list[str]) -> dict:
    cache = out / "da3_depth.npz"
    if cache.exists():
        z = np.load(cache)
        return {k: z[k] for k in z.files}
    import torch
    from depth_anything_3.api import DepthAnything3
    model = DepthAnything3.from_pretrained(DA3_MODEL).to("cuda" if torch.cuda.is_available() else "cpu").eval()
    cam = next(iter(rec.cameras.values()))
    res = {}
    for name in names:
        rgb = cv2.cvtColor(cv2.imread(str(out / "images" / name)), cv2.COLOR_BGR2RGB)
        with torch.no_grad():
            pred = model.inference([rgb])
        d = pred.depth[0].astype(np.float32)
        f_proc = cam.mean_focal_length() * d.shape[1] / cam.width
        res[name] = d * f_proc / 300.0
    np.savez_compressed(cache, **res)
    return res


def _scale_from_sfm(rec, depths: dict) -> tuple[float, float]:
    ratios = []
    for img in rec.images.values():
        if img.name not in depths or not img.has_pose:
            continue
        D = depths[img.name]
        cam = rec.cameras[img.camera_id]
        sx, sy = D.shape[1] / cam.width, D.shape[0] / cam.height
        T = img.cam_from_world().matrix() if callable(img.cam_from_world) else img.cam_from_world.matrix()
        for p2 in img.points2D:
            if not p2.has_point3D():
                continue
            X = rec.points3D[p2.point3D_id].xyz
            z = (T[:3, :3] @ X + T[:3, 3])[2]
            u, v = int(p2.xy[0] * sx), int(p2.xy[1] * sy)
            if z > 0 and 0 <= v < D.shape[0] and 0 <= u < D.shape[1] and D[v, u] > 0.2:
                ratios.append(D[v, u] / z)
    r = np.array(ratios)
    s = float(np.median(r))
    spread = float(np.median(np.abs(r / s - 1)))      # relative MAD of the scale votes
    return s, spread


def fuse_video(out: Path, rec, depths: dict, scale: float, stride: int = 4, max_range: float = 6.0,
               ray_samples: int = 400):
    rng = np.random.default_rng(0)
    pts, cams, rays = [], [], []
    for img in sorted(rec.images.values(), key=lambda i: i.name):
        if img.name not in depths or not img.has_pose:
            continue
        D = depths[img.name]
        cam = rec.cameras[img.camera_id]
        sx = D.shape[1] / cam.width
        fx = cam.focal_length_x * sx if hasattr(cam, "focal_length_x") else cam.mean_focal_length() * sx
        fy = cam.focal_length_y * sx if hasattr(cam, "focal_length_y") else fx
        cx, cy = cam.principal_point_x * sx, cam.principal_point_y * sx
        T = img.cam_from_world().matrix() if callable(img.cam_from_world) else img.cam_from_world.matrix()
        Tcw = np.eye(4); Tcw[:3, :4] = T
        Tcw[:3, 3] *= scale
        Twc = np.linalg.inv(Tcw)
        gy, gx = np.gradient(D)
        edge = np.hypot(gx, gy) / np.maximum(D, 1e-3) > 0.05     # depth discontinuities -> flying pixels
        vs, us = np.mgrid[0:D.shape[0]:stride, 0:D.shape[1]:stride]
        d = D[vs, us]; m = (d > 0.2) & (d < max_range) & ~edge[vs, us]
        u, v, d = us[m], vs[m], d[m]
        pc = np.stack([(u - cx) / fx * d, (v - cy) / fy * d, d, np.ones_like(d)])
        w = (Twc @ pc)[:3].T
        pts.append(w); cams.append(Twc[:3, 3])
        rays.append(w[rng.choice(len(w), min(ray_samples, len(w)), replace=False)] if len(w) else w)
    return np.concatenate(pts), np.array(cams), rays, [np.linalg.inv(np.r_[img.cam_from_world().matrix() if callable(img.cam_from_world) else img.cam_from_world.matrix(), [[0, 0, 0, 1]]]) for img in rec.images.values() if img.name in depths and img.has_pose]


def gravity_align(P: np.ndarray, cams: np.ndarray, cam_up_dirs: np.ndarray):
    """Rotate so that 'up' is +y. Initial up = mean camera up (OpenCV -y axis in world); refined to the floor normal."""
    import open3d as o3d
    up = cam_up_dirs.mean(0); up /= np.linalg.norm(up)
    h = P @ up
    below = P[h < np.median(cams @ up) - 0.6]
    if len(below) > 2000:
        pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(below)).voxel_down_sample(0.03)
        best = None
        rest = pcd
        for _ in range(4):        # a few largest planes; floor = most horizontal w.r.t. initial up, lowest
            if len(rest.points) < 500:
                break
            o3d.utility.random.seed(0)
            plane, inl = rest.segment_plane(0.02, 3, 500)
            n = np.array(plane[:3]); n /= np.linalg.norm(n)
            if np.dot(n, up) < 0:
                n = -n
            if np.degrees(np.arccos(np.clip(np.dot(n, up), -1, 1))) < 20 and (best is None or len(inl) > best[1]):
                best = (n, len(inl))
            rest = rest.select_by_index(inl, invert=True)
        if best is not None:
            up = best[0]
    y = up
    x = np.cross([0, 0, 1.0], y)
    if np.linalg.norm(x) < 1e-6:
        x = np.cross([1.0, 0, 0], y)
    x /= np.linalg.norm(x); z = np.cross(x, y)
    R = np.stack([x, y, z])          # rows: new axes in old coords
    return R


def _load_images(paths):
    return [cv2.cvtColor(cv2.imread(str(p)), cv2.COLOR_BGR2RGB) for p in paths]


def da3_front(out: Path, frames: list[Path]):
    """Cached DA3 chunked poses + metric scale."""
    cache = out / "da3_chain.npz"
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        cast = lambda arr, dt: [None if x is None else np.asarray(x, dtype=dt) for x in arr]
        return (cast(z["Twc"], np.float64), cast(z["D"], np.float32), cast(z["K"], np.float64),
                cast(z["C"], np.float32), float(z["scale"]), float(z["spread"]))
    from ..geometry.da3_frontend import chunked_poses, metric_scale
    imgs = _load_images(frames)
    Twc, D, K, C = chunked_poses(imgs)
    scale, spread, _ = metric_scale(imgs, D, K)
    np.savez_compressed(cache, Twc=np.array(Twc, dtype=object), D=np.array(D, dtype=object),
                        K=np.array(K, dtype=object), C=np.array(C, dtype=object), scale=scale, spread=spread)
    return Twc, D, K, C, scale, spread


def run(capture: Path, drift_correction: bool = True, fps: float = 3.0, width: int = 960,
        frontend: str = "da3") -> PropertyPlan:
    from ..geometry.backend import plan_from_cloud
    from ..geometry.da3_frontend import fuse_frames
    clip = _clip_path(capture)
    out = _cache_dir(clip, fps, width)
    frames = extract_keyframes(clip, out, fps=fps, width=width)
    warnings = []
    if frontend == "colmap":
        rec = run_sfm(out)
        names = [img.name for img in rec.images.values() if img.has_pose]
        depths = metric_depths(out, rec, names)
        scale, spread = _scale_from_sfm(rec, depths)
        P, cams, rays, Twcs = fuse_video(out, rec, depths, scale)
        registered = len(names)
    else:
        Twc, D, K, C, scale, spread = da3_front(out, frames)
        P, cams, rays, Twcs = fuse_frames(Twc, D, K, C, scale)
        registered = sum(T is not None for T in Twc)
    import open3d as o3d
    P = np.asarray(o3d.geometry.PointCloud(o3d.utility.Vector3dVector(P)).voxel_down_sample(0.015).points)
    cam_up = np.array([-T[:3, 1] for T in Twcs])       # OpenCV camera y points down
    R = gravity_align(P, cams, cam_up)
    P, cams = P @ R.T, cams @ R.T
    rays = [r @ R.T for r in rays]
    reg_frac = registered / max(len(frames), 1)
    if reg_frac < 0.8:
        warnings.append(f"only {reg_frac:.0%} of keyframes have poses; unposed parts of the walk are missing")
    if drift_correction:
        warnings.append("drift: chunk chaining by shared-frame similarity alignment; no global loop closure yet")
    q = float(np.clip((1 - 3 * spread) * reg_frac, 0.2, 1.0))
    quality = {"frontend": frontend, "keyframes": len(frames), "registered": int(registered),
               "metric_scale": round(scale, 5), "scale_vote_rel_mad": round(spread, 4)}
    (out / f"frontend_{frontend}.json").write_text(json.dumps(quality, indent=1))
    cid = clip.parent.name if clip.name == "rgb.mp4" else clip.stem
    return plan_from_cloud(P, cams, rays, cid, "video", warnings, quality, quality_scale=q)