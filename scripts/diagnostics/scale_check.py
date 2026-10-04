"""Is our LiDAR-tier cloud metrically scaled? Similarity ICP (with scale) of our fused cloud onto the laser scan.
uv run python scripts/diagnostics/scale_check.py <stray_capture> <laser.ply> [...]
"""
import sys
from pathlib import Path
import numpy as np, open3d as o3d
from roomscan.tiers.lidar import fused
from roomscan.geometry.planes import horizontal_planes, estimate_yaw, rotate_y
from roomscan.bench.repeat import register

cap, lasers = Path(sys.argv[1]), sys.argv[2:]
L = np.concatenate([np.asarray(o3d.io.read_point_cloud(p).voxel_down_sample(0.02).points) for p in lasers])
L = np.c_[L[:, 0], L[:, 2], -L[:, 1]]                 # z-up -> y-up (as in laser_gt.py)
hl = horizontal_planes(L, float(np.median(L[:, 1])))
if hl.floor_y > np.median(L[:, 1]):
    L[:, 1] *= -1; L[:, 2] *= -1; hl = horizontal_planes(L, float(np.median(L[:, 1])))
L = rotate_y(L, estimate_yaw(L, hl)[0])
P, cams, _ = fused(cap, drift=True)
hq = horizontal_planes(P, float(np.median(cams[:, 1])))
P = rotate_y(P, estimate_yaw(P, hq)[0])
bl = L[(L[:, 1] > hl.floor_y + 0.95) & (L[:, 1] < hl.floor_y + 1.6)]
bq = P[(P[:, 1] > hq.floor_y + 0.95) & (P[:, 1] < hq.floor_y + 1.6)]
M, _ = register(bl[:, [0, 2]], bq[:, [0, 2]])
T0 = np.eye(4); T0[0, 0], T0[0, 2], T0[2, 0], T0[2, 2] = M[0, 0], M[0, 1], M[1, 0], M[1, 1]
T0[0, 3], T0[2, 3] = M[0, 2], M[1, 2]; T0[1, 3] = hl.floor_y - hq.floor_y
src = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(P)).voxel_down_sample(0.03)
dst = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(L)).voxel_down_sample(0.03)
reg = o3d.pipelines.registration
T = T0
for thr in (0.2, 0.1, 0.05, 0.03):
    r = reg.registration_icp(src, dst, thr, T, reg.TransformationEstimationPointToPoint(with_scaling=True),
                             reg.ICPConvergenceCriteria(max_iteration=60))
    T = r.transformation
s = float(np.cbrt(np.linalg.det(T[:3, :3])))
print(f"similarity ICP: scale {s:.4f} (our cloud is {(1/s-1)*100:+.2f}% vs laser), fitness {r.fitness:.3f}, rmse {r.inlier_rmse*100:.2f} cm")
print(f"floor-to-floor offset check: our floor {hq.floor_y:.3f}, laser floor {hl.floor_y:.3f}, laser ceiling h {hl.ceiling_height}")
