"""Fit per-tier interval half-widths from measured errors (split-conformal style, 90% nominal).

Sources (no tape ground truth for the sample data):
  video/photo: |dimension error| vs the LiDAR plan of the same capture (benchmark/results/benchmark_sample.json)
  lidar: room-dimension disagreement between two captures of the same flat on rooms partitioned identically
         (fixloop/after/room_dims.txt, IoU >= 0.9), halved because each capture contributes error
With fewer than 5 residuals we refuse to shrink: half-width = max(default, 1.25 x worst observed error).
Writes benchmark/calibration.json, which calibration.load() picks up.
"""
import json, re
from pathlib import Path
import numpy as np
from roomscan.calibration import DEFAULT_REL, conformal_quantile

bench = json.loads(Path("benchmark/results/benchmark_sample.json").read_text())
res = {"video": [], "photo": []}
for key, rows in bench["details"].items():
    tier = key.split("/")[0]
    res[tier] += [abs(r["err_pct"]) / 100 for r in rows]
lid = []
for line in Path("fixloop/after/room_dims.txt").read_text().splitlines():
    m = re.search(r"diff=\s*([\d.]+) cm\s+IoU=([\d.]+)", line)
    a = re.search(r"A=([\d.]+)", line)
    if m and a and float(m.group(2)) >= 0.9:
        lid.append(float(m.group(1)) / 100 / 2 / float(a.group(1)))
res["lidar"] = lid
# Prefer laser ground truth for LiDAR when available (own benchmark): cross-capture agreement underestimates true error
laser = [abs(w["err_pct"]) / 100 for p in Path("benchmark/results/own").glob("laser_gt_ark*.json")
         for w in json.loads(p.read_text())["walls"] if w.get("gt_m") and abs(w["err_pct"]) < 100]
laser_walls = [w for p in Path("benchmark/results/own").glob("laser_gt_ark*.json")
               for w in json.loads(p.read_text())["walls"] if w.get("gt_m") and w["gt_m"] > 0.3]
lidar_abs = None
if len(laser_walls) >= 5:
    # errors are ~constant in cm (wrong-face picks), so model half-width = max(rel x L, abs)
    res["lidar"] = [abs(w["err_pct"]) / 100 for w in laser_walls if w["gt_m"] >= 2.0] or res["lidar"]
    lidar_abs = conformal_quantile(np.array([abs(w["err_cm"]) / 100 for w in laser_walls]), 0.90)
cal, report = {}, {}
for tier, r in res.items():
    r = np.array(r)
    base = DEFAULT_REL[tier]["wall"]
    if len(r) >= 5:
        w = conformal_quantile(r, 0.90)
        how = f"conformal q90 of {len(r)} residuals"
    elif len(r):
        w = max(base, 1.25 * float(r.max()))
        how = f"{len(r)} residuals (<5): max(default, 1.25 x worst)"
    else:
        w = base; how = "no residuals: default"
    ratio = w / base
    cal[tier] = {k: float(v * ratio) for k, v in DEFAULT_REL[tier].items()}
    cal[tier]["wall"] = float(w)
    report[tier] = {"wall_rel_halfwidth": round(w, 4), "method": how, "residuals": [round(float(x), 4) for x in r]}
if lidar_abs is not None:
    cal["lidar"]["wall_abs"] = float(lidar_abs); report["lidar"]["wall_abs_m"] = round(float(lidar_abs), 4)
Path("benchmark/calibration.json").write_text(json.dumps(cal, indent=1))
Path("benchmark/results/calibration_fit.json").write_text(json.dumps(report, indent=1))
print(json.dumps(report, indent=1))
