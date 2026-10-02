"""Room segmentation debug run.
uv run python scripts/rooms_check.py <capture_dir> <out_dir>
"""
import sys, json
from pathlib import Path
import numpy as np
import open3d as o3d
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from roomscan.geometry.pointcloud import fuse
from roomscan.geometry.planes import horizontal_planes, manhattan_yaw, rotate_y, wall_slice
from roomscan.geometry.rooms import segment_rays
from roomscan.geometry.snap import snap_rooms_local

cap, out = Path(sys.argv[1]), Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
cache = out / "fused_rays.npz"
if cache.exists():
    z = np.load(cache); P, cams = z["P"], z["cams"]
    rays = np.split(z["R"], z["off"])
else:
    pts, cams, rays = fuse(cap, stride=6)
    P = np.asarray(o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts)).voxel_down_sample(0.015).points)
    np.savez_compressed(cache, P=P, cams=cams, R=np.concatenate(rays), off=np.cumsum([len(r) for r in rays])[:-1])

hp = horizontal_planes(P, cam_y=float(np.median(cams[:, 1])))
yaw, _ = manhattan_yaw(wall_slice(P, hp))
P, cams = rotate_y(P, yaw), rotate_y(cams, yaw)
rays = [rotate_y(r, yaw) for r in rays]

g, labels, wall, free = segment_rays(P, cams, rays, hp.floor_y, hp.ceiling_y)
rooms = snap_rooms_local(g, labels, P, hp.floor_y, hp.ceiling_y, wall); xs = zs = []
print("face lines x/z:", len(xs), len(zs), flush=True)

ext = [g.x0, g.x0 + g.shape[1] * g.res, g.z0, g.z0 + g.shape[0] * g.res]
fig, ax = plt.subplots(figsize=(14, 14))
ax.imshow(wall, origin="lower", extent=ext, cmap="Greys", alpha=0.5)
for x in xs: ax.axvline(x, color="0.85", lw=0.3)
for z_ in zs: ax.axhline(z_, color="0.85", lw=0.3)
summary = {"floor_y": hp.floor_y, "ceiling_height_global": hp.ceiling_height, "yaw_deg": float(np.degrees(yaw)),
           "n_lines": [len(xs), len(zs)], "rooms": []}
cmap = plt.get_cmap("tab10")
for r in rooms:
    xs_ = [p[0] for p in r.polygon] + [r.polygon[0][0]]; zs_ = [p[1] for p in r.polygon] + [r.polygon[0][1]]
    ax.fill(xs_, zs_, color=cmap(r.label % 10), alpha=0.3)
    ax.plot(xs_, zs_, "-", color=cmap(r.label % 10), lw=2)
    ax.text(np.mean(xs_[:-1]), np.mean(zs_[:-1]),
            f"R{r.label} {r.area_m2:.1f}m2" + (f"\nh={r.ceiling_height:.3f}" if r.ceiling_height else ""),
            ha="center", fontsize=11, weight="bold")
    for i, L in enumerate(r.wall_lengths):
        if L < 0.3: continue
        p, q = r.polygon[i], r.polygon[(i + 1) % len(r.polygon)]
        ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, f"{L:.2f}", fontsize=8,
                color="blue" if r.wall_support[i] > 0.5 else "red")
    summary["rooms"].append({"id": r.label, "area_m2": round(r.area_m2, 3), "ceiling_h": r.ceiling_height,
                             "ceiling_spread": r.ceiling_spread, "n_walls": len(r.wall_lengths),
                             "walls": [round(x, 3) for x in r.wall_lengths],
                             "support": [round(x, 2) for x in r.wall_support]})
ax.plot(cams[:, 0], cams[:, 2], "c-", lw=0.4)
ax.set_aspect("equal"); plt.tight_layout(); plt.savefig(out / "rooms.png", dpi=90)
(out / "rooms.json").write_text(json.dumps(summary, indent=1))
for r in summary["rooms"]:
    print(r["id"], r["area_m2"], r["ceiling_h"] and round(r["ceiling_h"], 3), r["n_walls"], r["walls"])
