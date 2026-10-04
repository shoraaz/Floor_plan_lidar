"""Sanity-check axis conventions and geometry on real captures.

uv run python scripts/diagnostics/explore_lidar.py <capture_dir> <out_dir>
Writes: cloud.ply, height_hist.png, topdown.png, stats.txt
"""
import sys
from pathlib import Path
import numpy as np
import open3d as o3d
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from roomscan.geometry.pointcloud import fuse

cap, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)

pts, cams = fuse(cap, stride=6)
pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts)).voxel_down_sample(0.02)
P = np.asarray(pcd.points)
o3d.io.write_point_cloud(str(out / "cloud.ply"), pcd)

lines = [f"frames used: {len(cams)}  raw pts: {len(pts)}  voxel pts: {len(P)}",
         f"camera path length m: {np.linalg.norm(np.diff(cams, axis=0), axis=1).sum():.2f}",
         f"start-end camera gap m: {np.linalg.norm(cams[-1] - cams[0]):.3f}",
         f"cam height (y) mean: {cams[:,1].mean():.3f}"]
for i, ax in enumerate("xyz"):
    lines.append(f"{ax}: p1={np.percentile(P[:,i],1):.3f} p99={np.percentile(P[:,i],99):.3f}")

# height histogram along y (ARKit gravity-up axis)
hist, edges = np.histogram(P[:, 1], bins=np.arange(P[:, 1].min(), P[:, 1].max() + 0.01, 0.01))
top = np.argsort(hist)[::-1][:6]
lines.append("top y-bins (height, count): " + ", ".join(f"({edges[i]:.3f},{hist[i]})" for i in sorted(top)))
plt.figure(figsize=(8, 3)); plt.plot(edges[:-1], hist); plt.xlabel("y (m)"); plt.yscale("log"); plt.tight_layout()
plt.savefig(out / "height_hist.png", dpi=110); plt.close()

# top-down density of a mid-height slice (walls)
ylo, yhi = np.percentile(P[:, 1], 5), np.percentile(P[:, 1], 95)
mid = P[(P[:, 1] > ylo + 0.4) & (P[:, 1] < yhi - 0.4)]
plt.figure(figsize=(7, 7))
plt.hist2d(mid[:, 0], mid[:, 2], bins=300, cmap="magma", norm=matplotlib.colors.LogNorm())
plt.plot(cams[:, 0], cams[:, 2], "c-", lw=0.6)
plt.gca().set_aspect("equal"); plt.xlabel("x"); plt.ylabel("z"); plt.tight_layout()
plt.savefig(out / "topdown.png", dpi=110); plt.close()

(out / "stats.txt").write_text("\n".join(lines))
print("\n".join(lines))
