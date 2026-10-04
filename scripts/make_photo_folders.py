"""Build photo-tier inputs from a sample capture: one folder per room, N stills each.

The organisers' sample data has no separate photo sets, so the photo tier is benchmarked on stills taken
from the capture's own rgb.mp4 (same walk, same rooms). Room membership of each frame comes from the LiDAR
plan (camera position inside a room polygon). Only the selected JPEGs are used downstream: no depth, no poses,
no intrinsics, which is exactly the photo-tier input contract. Disclosed in the report.

uv run python scripts/make_photo_folders.py <stray_capture_dir> <lidar_plan.json> <out_dir> [per_room]
"""
import sys, json
from pathlib import Path
import numpy as np, cv2, pandas as pd
from shapely.geometry import Point, Polygon

cap, plan_p, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
per_room = int(sys.argv[4]) if len(sys.argv) > 4 else 6
plan = json.loads(plan_p.read_text())
yaw = np.radians(plan["input_quality"]["yaw_deg"])
odo = pd.read_csv(cap / "odometry.csv", skipinitialspace=True); odo.columns = [c.strip() for c in odo.columns]
xyz = odo[["x", "y", "z"]].to_numpy()
c, s = np.cos(-yaw), np.sin(-yaw)
xa, za = c * xyz[:, 0] - s * xyz[:, 2], s * xyz[:, 0] + c * xyz[:, 2]      # same rotation as planes.rotate_y
polys = {r["room_id"]: Polygon([w["start"] for w in r["walls"]]) for r in plan["rooms"]}
vid = cv2.VideoCapture(str(cap / "rgb.mp4"))
n = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))
# odometry row -> video frame: 1:1 for Stray (same rate); rescaled for low-rate poses (converted ARKitScenes, 10 Hz)
ts = odo["timestamp"].to_numpy(); rate = (len(ts) - 1) / max(ts[-1] - ts[0], 1e-6); vfps = vid.get(cv2.CAP_PROP_FPS) or rate
to_vid = (lambda i: int(round(i * vfps / rate))) if rate < 30 else (lambda i: i)
manifest = {}
for rid, poly in polys.items():
    if poly.area < 2.0:          # skip slivers/closets for the photo set
        continue
    step = 5 if rate >= 30 else 1
    inside = [i for i in range(0, len(xyz), step) if to_vid(i) < n and poly.contains(Point(xa[i], za[i]))]
    if len(inside) < per_room:
        continue
    # spread picks over the time spent in the room; within each slot keep the sharpest frame
    slots = np.array_split(np.array(inside), per_room)
    d = out / rid; d.mkdir(parents=True, exist_ok=True)
    picks = []
    for slot in slots:
        best, best_sharp = None, -1
        for i in slot[:: max(1, len(slot) // 6)]:
            vid.set(cv2.CAP_PROP_POS_FRAMES, to_vid(int(i))); ok, bgr = vid.read()
            if not ok:
                continue
            sharp = cv2.Laplacian(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
            if sharp > best_sharp:
                best, best_sharp = (int(i), bgr), sharp
        if best:
            cv2.imwrite(str(d / f"frame_{best[0]:06d}.jpg"), best[1], [cv2.IMWRITE_JPEG_QUALITY, 95])
            picks.append(best[0])
    manifest[rid] = picks
(out / "manifest.json").write_text(json.dumps({"source": str(cap), "per_room": per_room, "rooms": manifest}, indent=1))
print({k: len(v) for k, v in manifest.items()})
