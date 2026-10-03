import sys, numpy as np
from pathlib import Path
from roomscan.geometry.pointcloud import fuse
P, C, _ = fuse(Path(sys.argv[1]), stride=6)
print("camera position std per axis (x,y,z):", np.round(C.std(0), 3))
for a, n in enumerate("xyz"):
    h, e = np.histogram(P[:, a], bins=np.arange(P[:, a].min(), P[:, a].max() + 0.02, 0.02))
    top = np.sort(h)[::-1][:2] / len(P) * 100
    print(f"{n}: range {np.ptp(P[:, a]):.2f} m, two largest 2cm-bins hold {top[0]:.1f}% and {top[1]:.1f}% of points")
