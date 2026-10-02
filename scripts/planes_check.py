"""Run floor/ceiling + Manhattan alignment on explored clouds.
uv run python scripts/planes_check.py
"""
from pathlib import Path
import numpy as np
import open3d as o3d
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from roomscan.geometry.planes import horizontal_planes, manhattan_yaw, rotate_y, wall_slice

rows = []
fig, axes = plt.subplots(1, 3, figsize=(18, 6))
for ax, k in zip(axes, ["single_room", "floor_only", "with_ceiling"]):
    P = np.asarray(o3d.io.read_point_cloud(f"out/explore/{k}/cloud.ply").points)
    hp = horizontal_planes(P, cam_y=0.0)
    W = wall_slice(P, hp)
    yaw, conc = manhattan_yaw(W)
    Wr = rotate_y(W, yaw)
    ax.hist2d(Wr[:, 0], Wr[:, 2], bins=400, cmap="magma", norm=matplotlib.colors.LogNorm())
    ax.set_aspect("equal"); ax.set_title(f"{k} yaw={np.degrees(yaw):.1f}")
    ch = hp.ceiling_height
    rows.append(f"{k:13s} floor_y={hp.floor_y:.3f} (spread {hp.floor_spread_m*100:.1f}cm)  "
                f"ceiling_y={'-' if hp.ceiling_y is None else f'{hp.ceiling_y:.3f}'}  "
                f"ceiling_h={'-' if ch is None else f'{ch:.3f}m'}  "
                f"yaw={np.degrees(yaw):.2f}deg conc={conc:.2f}  wall_pts={len(W)}")
plt.tight_layout(); plt.savefig("out/explore/aligned.png", dpi=100)
Path("out/explore/planes.txt").write_text("\n".join(rows)); print("\n".join(rows))
