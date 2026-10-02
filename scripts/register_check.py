"""Are two captures the same place? Register their Manhattan-aligned wall maps (4 rotations x FFT translation search).
uv run python scripts/register_check.py out/rooms/with_ceiling out/rooms/floor_only
"""
import sys
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve
from roomscan.geometry.planes import horizontal_planes, manhattan_yaw, rotate_y, wall_slice

RES = 0.05


def wall_map(d: Path):
    z = np.load(d / "fused_rays.npz"); P, cams = z["P"], z["cams"]
    hp = horizontal_planes(P, cam_y=float(np.median(cams[:, 1])))
    yaw, _ = manhattan_yaw(wall_slice(P, hp))
    P = rotate_y(P, yaw)
    B = P[(P[:, 1] > hp.floor_y + 1.1) & (P[:, 1] < hp.floor_y + 2.0)][:, [0, 2]]
    return B


def grid(B, x0, z0, shape):
    G = np.zeros(shape, np.float32)
    c = ((B[:, 0] - x0) / RES).astype(int); r = ((B[:, 1] - z0) / RES).astype(int)
    ok = (r >= 0) & (r < shape[0]) & (c >= 0) & (c < shape[1])
    np.add.at(G, (r[ok], c[ok]), 1)
    return (G >= 2).astype(np.float32)


A = wall_map(Path(sys.argv[1])); Bpts = wall_map(Path(sys.argv[2]))
ga_x0, ga_z0 = A[:, 0].min(), A[:, 1].min()
shapeA = (int(np.ptp(A[:, 1]) / RES) + 2, int(np.ptp(A[:, 0]) / RES) + 2)
GA = grid(A, ga_x0, ga_z0, shapeA)
best = None
for k in range(4):
    th = k * np.pi / 2
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    Br = Bpts @ R.T
    shapeB = (int(np.ptp(Br[:, 1]) / RES) + 2, int(np.ptp(Br[:, 0]) / RES) + 2)
    GB = grid(Br, Br[:, 0].min(), Br[:, 1].min(), shapeB)
    corr = fftconvolve(GA, GB[::-1, ::-1], mode="full")
    i = np.unravel_index(np.argmax(corr), corr.shape)
    overlap = corr[i] / min(GA.sum(), GB.sum())
    print(f"rot {k*90:3d}deg: overlap {overlap:.3f}")
    if best is None or overlap > best[0]:
        best = (overlap, k * 90)
print(f"BEST rot={best[1]} overlap={best[0]:.3f}  (>0.5 strongly suggests same place; <0.2 different)")
