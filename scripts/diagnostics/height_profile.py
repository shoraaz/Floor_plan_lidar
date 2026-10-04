"""Point-height profile per capture (relative to floor): what part of the walls each walk observed."""
import sys, numpy as np
from pathlib import Path
from roomscan.tiers.lidar import fused
from roomscan.geometry.planes import horizontal_planes
for k in sys.argv[1:]:
    P, c, _ = fused(Path(k)); hp = horizontal_planes(P, float(np.median(c[:, 1]))); h = P[:, 1] - hp.floor_y
    b = np.arange(0, 3.2, 0.2); n, _ = np.histogram(h, b)
    print(Path(k).parent.name, "total", len(P))
    print("   " + " ".join(f"{b[i]:.1f}:{n[i]/len(P)*100:.1f}%" for i in range(len(n))))
