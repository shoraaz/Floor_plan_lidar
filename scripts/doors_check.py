"""Debug view of structure-only segmentation: wall map, detected doorways (red), room labels.
uv run python scripts/doors_check.py <capture_dir> <out_png>
"""
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from roomscan.tiers.lidar import fused
from roomscan.geometry.planes import horizontal_planes, manhattan_yaw, rotate_y, wall_slice
from roomscan.geometry.rooms import segment_structure

cap, out = Path(sys.argv[1]), Path(sys.argv[2])
P, cams, rays = fused(cap)
hp = horizontal_planes(P, cam_y=float(np.median(cams[:, 1])))
yaw, _ = manhattan_yaw(wall_slice(P, hp))
P, cams = rotate_y(P, yaw), rotate_y(cams, yaw); rays = [rotate_y(r, yaw) for r in rays]
g, labels, closed, free, doors = segment_structure(P, cams, rays, hp.floor_y, hp.ceiling_y)
img = np.ones(g.shape + (3,))
lab = np.ma.masked_where(labels == 0, labels)
fig, ax = plt.subplots(figsize=(13, 13))
ax.imshow(lab, origin="lower", cmap="tab20", alpha=0.5)
wall_only = np.ma.masked_where(~closed, closed)
ax.imshow(wall_only, origin="lower", cmap="Greys", vmin=0, vmax=1)
for d in doors:
    (r0, r1), (c0, c1) = d["rows"], d["cols"]
    ax.add_patch(plt.Rectangle((c0, r0), c1 - c0 + 1, r1 - r0 + 1, color="red"))
    ax.text(c1 + 3, r1 + 3, f"{d['width_m']:.2f}", color="red", fontsize=8)
cr = ((cams[:, 2] - g.z0) / g.res); cc = ((cams[:, 0] - g.x0) / g.res)
ax.plot(cc, cr, "c-", lw=0.4)
ax.set_title(f"{len(doors)} doorways, {labels.max()} rooms")
plt.tight_layout(); plt.savefig(out, dpi=80)
print(len(doors), "doors;", labels.max(), "rooms")
