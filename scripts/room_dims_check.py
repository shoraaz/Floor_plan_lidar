"""Diagnostic: per matched room, compare wall-to-wall extents (what a tape measures) between two captures.
uv run python scripts/room_dims_check.py <capA> <capB> <planA> <planB>
"""
import sys, json
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon
from roomscan.bench.repeat import aligned_band, register, _apply

ca, cb, pa, pb = sys.argv[1:5]
M, diag = register(aligned_band(Path(ca)), aligned_band(Path(cb)))
PA, PB = json.loads(Path(pa).read_text()), json.loads(Path(pb).read_text())
polyB = [(r, _apply(M, [w["start"] for w in r["walls"]])) for r in PB["rooms"]]
print("residual rot", round(diag["residual_rot_deg"], 3))
rows = []
for ra in PA["rooms"]:
    A = np.array([w["start"] for w in ra["walls"]]); pA = Polygon(A).buffer(0)
    best = max(polyB, key=lambda t: pA.intersection(Polygon(t[1]).buffer(0)).area / pA.union(Polygon(t[1]).buffer(0)).area)
    pB = Polygon(best[1]).buffer(0); iou = pA.intersection(pB).area / pA.union(pB).area
    if iou < 0.5:
        continue
    B = best[1]
    ea, eb = np.ptp(A, 0), np.ptp(B, 0)
    for ax, name in ((0, "x-extent"), (1, "z-extent")):
        d = abs(ea[ax] - eb[ax])
        rows.append((ra["room_id"], best[0]["room_id"], name, ea[ax], eb[ax], d, round(iou, 2)))
for r in rows:
    print(f"{r[0]:7s}~{r[1]:7s} {r[2]} A={r[3]:.3f} B={r[4]:.3f} diff={r[5]*100:6.1f} cm  IoU={r[6]}")
d = np.array([r[5] for r in rows])
print(f"median diff {np.median(d)*100:.1f} cm; within 1cm: {(d<=0.01).sum()}/{len(d)}; within 5cm: {(d<=0.05).sum()}/{len(d)}")
