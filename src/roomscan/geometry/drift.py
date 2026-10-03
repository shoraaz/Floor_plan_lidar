"""Drift accountability for the LiDAR tier: start-end loop closure, correction distributed along the walk.

ARKit VIO drifts slowly; a protocol-following walk ends where it started (capture protocol rule), so:
  1. build a local cloud from the first and last `win` seconds of the walk (same world frame, raw poses)
  2. ICP (point-to-plane, coarse-to-fine) the END submap onto the START submap -> T_corr = accumulated drift
  3. accept only if the ICP is confident (fitness, rmse) and the correction is small enough to be drift, not a
     mis-registration (< 0.6 m, < 5 deg)
  4. distribute: frame i at arc-length fraction a gets  T_i' = Interp(I, T_corr, a) @ T_i
     (rotation slerp, translation linear): the closed-form optimum of a pose graph with one loop edge and
     uniform odometry weights
If no confident loop is found, poses stay as reported and the plan says so (never silently "as-is").
"""
from __future__ import annotations
import numpy as np
import cv2
from scipy.spatial.transform import Rotation as R, Slerp


def _submap(frames, sel, backproject, scale_intrinsics, voxel=0.03):
    import open3d as o3d
    pts = []
    for i in sel:
        T, (fx, fy, cx, cy), dp, cp = frames[i]
        d = cv2.imread(str(dp), cv2.IMREAD_UNCHANGED)
        c = cv2.imread(str(cp), cv2.IMREAD_UNCHANGED) if cp else None
        pts.append(backproject(d, c, scale_intrinsics(fx, fy, cx, cy, d.shape[1], d.shape[0]), T, max_range_m=4.0))
    pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(np.concatenate(pts))).voxel_down_sample(voxel)
    pcd.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
    return pcd


def loop_correction(frames, win: int = 25, max_t: float = 0.6, max_rot_deg: float = 5.0):
    """Return (T_corr 4x4 or None, info dict). `frames` from load_stray (already strided)."""
    import open3d as o3d
    from .pointcloud import backproject
    from ..tiers.lidar import scale_intrinsics
    n = len(frames)
    if n < 3 * win:
        return None, {"loop": "too few frames"}
    c0, c1 = frames[0][0][:3, 3], frames[-1][0][:3, 3]
    gap = float(np.linalg.norm(c1 - c0))
    if gap > 2.0:
        return None, {"loop": f"walk does not return to start (gap {gap:.2f} m)", "gap_m": gap}
    A = _submap(frames, range(0, win), backproject, scale_intrinsics)
    B = _submap(frames, range(n - win, n), backproject, scale_intrinsics)
    T = np.eye(4)
    reg = None
    for thr in (0.20, 0.08, 0.03):
        reg = o3d.pipelines.registration.registration_icp(
            B, A, thr, T, o3d.pipelines.registration.TransformationEstimationPointToPlane())
        T = reg.transformation
    t = float(np.linalg.norm(T[:3, 3]))
    rot = float(np.degrees(np.linalg.norm(R.from_matrix(T[:3, :3]).as_rotvec())))
    info = {"gap_m": gap, "icp_fitness": float(reg.fitness), "icp_rmse_m": float(reg.inlier_rmse),
            "corr_t_m": t, "corr_rot_deg": rot}
    if reg.fitness < 0.3 or reg.inlier_rmse > 0.02 or t > max_t or rot > max_rot_deg:
        info["loop"] = "rejected (low-confidence or implausible correction)"
        return None, info
    info["loop"] = "accepted"
    return T, info


def apply_correction(frames, T_corr):
    """Distribute T_corr along the walk by arc length (pose-graph optimum for a single loop)."""
    C = np.array([f[0][:3, 3] for f in frames])
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))]
    a = s / max(s[-1], 1e-9)
    sl = Slerp([0, 1], R.from_matrix(np.stack([np.eye(3), T_corr[:3, :3]])))
    out = []
    for (T, K, dp, cp), ai in zip(frames, a):
        D = np.eye(4); D[:3, :3] = sl(ai).as_matrix(); D[:3, 3] = ai * T_corr[:3, 3]
        out.append((D @ T, K, dp, cp))
    return out



# --------------------------------------------------------------------------------------------------
# v2: pose graph with revisit loop closures (replaces start-end only, which was rejected on all samples:
# start and end windows look in different directions, ICP had no overlap).
# --------------------------------------------------------------------------------------------------

def find_revisits(frames, min_gap: int = 100, max_dist: float = 0.6, max_angle_deg: float = 25.0, max_loops: int = 12):
    """Node pairs (i, j) far apart in time but close in position AND viewing direction."""
    C = np.array([f[0][:3, 3] for f in frames])
    V = np.array([f[0][:3, 2] for f in frames])          # camera +z (forward) in world, OpenCV frame
    cos_t = np.cos(np.radians(max_angle_deg))
    cands = []
    for j in range(min_gap, len(frames)):
        i_max = j - min_gap
        d = np.linalg.norm(C[:i_max + 1] - C[j], axis=1)
        ok = (d < max_dist) & (V[:i_max + 1] @ V[j] > cos_t)
        if ok.any():
            i = int(np.argmin(np.where(ok, d, np.inf)))
            cands.append((float(d[i]), i, j))
    # spread loops along the walk: greedy, keep pairs whose j are >= min_gap/2 apart
    cands.sort()
    chosen = []
    for d, i, j in cands:
        if all(abs(j - j2) >= min_gap // 2 for _, _, j2 in chosen):
            chosen.append((d, i, j))
        if len(chosen) >= max_loops:
            break
    return [(i, j) for _, i, j in chosen]


def pose_graph_correct(frames, half: int = 5):
    """Return (corrected frames or None, info). Strictly verified loops + robust global optimisation."""
    import open3d as o3d
    from .pointcloud import backproject
    from ..tiers.lidar import scale_intrinsics
    reg_ = o3d.pipelines.registration
    n = len(frames)
    P = [f[0] for f in frames]
    pairs = find_revisits(frames)
    loops = []
    for i, j in pairs:
        A = _submap(frames, range(max(0, i - half), min(n, i + half + 1)), backproject, scale_intrinsics)
        B = _submap(frames, range(max(0, j - half), min(n, j + half + 1)), backproject, scale_intrinsics)
        X = np.eye(4); r = None
        for thr in (0.10, 0.05, 0.02):
            r = reg_.registration_icp(B, A, thr, X, reg_.TransformationEstimationPointToPlane())
            X = r.transformation
        t = float(np.linalg.norm(X[:3, 3])); rot = float(np.degrees(np.linalg.norm(R.from_matrix(X[:3, :3]).as_rotvec())))
        ok = r.fitness > 0.5 and r.inlier_rmse < 0.015 and t < 0.3 and rot < 3.0   # strict: looser 0.35 accepted 5/5 loops and worsened floor spread 1.40->1.80 cm (benchmark/results/drift_ablation_loose035.log)
        loops.append({"i": i, "j": j, "fitness": round(float(r.fitness), 3), "rmse_cm": round(float(r.inlier_rmse) * 100, 2),
                      "t_cm": round(t * 100, 1), "rot_deg": round(rot, 3), "accepted": bool(ok)})
        if ok:
            loops[-1]["X"] = X
            loops[-1]["info"] = reg_.get_information_matrix_from_point_clouds(B, A, 0.02, X)
    acc = [l for l in loops if l["accepted"]]
    info = {"loops_tested": len(loops), "loops_accepted": len(acc),
            "loops": [{k: v for k, v in l.items() if k not in ("X", "info")} for l in loops]}
    if not acc:
        info["loop"] = "no verified revisit loop"
        return None, info
    pg = reg_.PoseGraph()
    for k in range(n):
        pg.nodes.append(reg_.PoseGraphNode(P[k].copy()))
    odo_info = np.eye(6) * 1e4
    for k in range(n - 1):
        pg.edges.append(reg_.PoseGraphEdge(k + 1, k, np.linalg.inv(P[k]) @ P[k + 1], odo_info, uncertain=False))
    for l in acc:
        i, j = l["i"], l["j"]
        pg.edges.append(reg_.PoseGraphEdge(j, i, np.linalg.inv(P[i]) @ l["X"] @ P[j], l["info"], uncertain=True))
    reg_.global_optimization(pg, reg_.GlobalOptimizationLevenbergMarquardt(),
                             reg_.GlobalOptimizationConvergenceCriteria(),
                             reg_.GlobalOptimizationOption(max_correspondence_distance=0.02, edge_prune_threshold=0.25,
                                                           reference_node=0))
    new = [(pg.nodes[k].pose, frames[k][1], frames[k][2], frames[k][3]) for k in range(n)]
    moved = [float(np.linalg.norm(pg.nodes[k].pose[:3, 3] - P[k][:3, 3])) for k in range(n)]
    info["loop"] = "accepted"
    info["max_node_shift_cm"] = round(max(moved) * 100, 1)
    info["mean_node_shift_cm"] = round(float(np.mean(moved)) * 100, 1)
    return new, info
