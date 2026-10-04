"""Drift accountability for the LiDAR tier: pose graph over ARKit keyframes with ICP-verified revisit loops.

Nodes = keyframes with their ARKit poses; odometry edges between consecutive keyframes; loop edges where the walk
revisits a place looking the same way, each verified by point-to-plane ICP of local submaps and accepted only under
strict thresholds; solved with Open3D global optimisation (line-process pruning). If no loop verifies, poses stay as
reported and the plan says so. Ablation: `roomscan run --no-drift-correction`, `scripts/drift_ablation.py`.
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
