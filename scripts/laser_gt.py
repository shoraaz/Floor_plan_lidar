"""Score a LiDAR-tier plan against laser-scanner ground truth (ARKitScenes Faro scans).

Ground truth definition (independent of our room logic):
  wall dimension  = distance between the two LASER wall faces that bound our reported room side pair
                    (each face = sub-cm median of laser points at the face peak nearest our side, room side)
  ceiling height  = laser floor-to-ceiling distance inside our room footprint
  door width      = gap between laser door-frame faces at our reported door (same 5 mm-bin rule)
Alignment of our plan to the laser frame: both clouds gravity- and Manhattan-aligned, then 4x90deg + FFT
translation + 2D ICP on the 0.95-1.6 m wall bands (bench/repeat.register). Alignment never moves our
dimensions; it only tells us which laser faces to measure.

uv run python scripts/laser_gt.py <stray_capture> <plan.json> <laser.ply> [more laser.ply ...] -> json + md
"""
import sys, json
from pathlib import Path
import numpy as np
import open3d as o3d
from roomscan.tiers.lidar import fused
from roomscan.geometry.planes import horizontal_planes, estimate_yaw, rotate_y
from roomscan.geometry.openings import refine_width
from roomscan.bench.repeat import register, _apply
from shapely.geometry import Polygon, Point

cap, plan_p, lasers = Path(sys.argv[1]), Path(sys.argv[2]), [Path(p) for p in sys.argv[3:] if not p.startswith("--")]
plan = json.loads(plan_p.read_text())

# ---- laser cloud: load, voxelise, put gravity on +y, Manhattan-align -------------------------------------
import hashlib
_key = hashlib.sha1("|".join(str(p.resolve()) for p in lasers).encode()).hexdigest()[:12]
_cache = Path("cache") / f"laser_{_key}.npz"
if _cache.exists():
    L = np.load(_cache)["L"]
else:
    pts = []
    for lp in lasers:
        pc = o3d.io.read_point_cloud(str(lp)).voxel_down_sample(0.01)
        pts.append(np.asarray(pc.points))
    L = np.concatenate(pts)
    Path("cache").mkdir(exist_ok=True); np.savez(_cache, L=L.astype(np.float32))
L = L.astype(np.float64)
def sharp(a):
    h, _ = np.histogram(L[:, a], bins=np.arange(L[:, a].min(), L[:, a].max() + 0.02, 0.02)); return np.sort(h)[-1] / len(L)
up = int(np.argmax([sharp(a) for a in range(3)]))
if up == 2:
    L = np.c_[L[:, 0], L[:, 2], -L[:, 1]]
elif up == 0:
    L = np.c_[L[:, 1], L[:, 0], -L[:, 2]]
hp = horizontal_planes(L, cam_y=float(np.median(L[:, 1])))
if hp.floor_y > np.median(L[:, 1]):        # flipped: floor above median -> invert up
    L[:, 1] *= -1; L[:, 2] *= -1
    hp = horizontal_planes(L, cam_y=float(np.median(L[:, 1])))
yaw, _ = estimate_yaw(L, hp)
L = rotate_y(L, yaw)
Lband = L[(L[:, 1] > hp.floor_y + 0.95) & (L[:, 1] < hp.floor_y + 1.6)]
# GT wall faces are measured ABOVE furniture: real walls reach the ceiling, cabinets/shelves usually do not.
top_gt = (hp.ceiling_y - 0.10) if hp.ceiling_y is not None else hp.floor_y + 2.3
Lhigh = L[(L[:, 1] > hp.floor_y + 1.8) & (L[:, 1] < top_gt)]
Lceil = L[np.abs(L[:, 1] - hp.ceiling_y) < 0.08] if hp.ceiling_y is not None else None

# ---- our capture in the plan frame (same steps as the backend) ----------------------------------------
P, cams, _ = fused(cap, drift=plan["input_quality"].get("drift_correction", True))
hq = horizontal_planes(P, cam_y=float(np.median(cams[:, 1])))
yq, _ = estimate_yaw(P, hq)
P = rotate_y(P, yq)
Qband = P[(P[:, 1] > hq.floor_y + 0.95) & (P[:, 1] < hq.floor_y + 1.6)]
M, diag = register(Lband[:, [0, 2]], Qband[:, [0, 2]])          # maps plan (x,z) -> laser (x,z)


def laser_face(p, q, centre, win=0.25, bin_m=0.005):
    """Laser face nearest our side p->q (already in laser frame), on the room side."""
    horiz = abs(q[1] - p[1]) < abs(q[0] - p[0])
    ax_f, ax_r = (2, 0) if horiz else (0, 2)
    fixed = (p[1] + q[1]) / 2 if horiz else (p[0] + q[0]) / 2
    lo, hi = sorted([p[0], q[0]] if horiz else [p[1], q[1]]); sh = 0.15 * (hi - lo)
    sel = Lhigh[(Lhigh[:, ax_r] > lo + sh) & (Lhigh[:, ax_r] < hi - sh) & (np.abs(Lhigh[:, ax_f] - fixed) < win)]
    if len(sel) < 30:
        return None, False
    v = sel[:, ax_f]; e = np.arange(fixed - win, fixed + win + bin_m, bin_m)
    h, _ = np.histogram(v, bins=e)
    from scipy.ndimage import gaussian_filter1d
    from scipy.signal import find_peaks
    h = gaussian_filter1d(h.astype(float), 1.0)
    pk, _ = find_peaks(h, height=0.4 * h.max(), distance=4)
    if not len(pk):
        return None, False
    c = (e[pk] + e[pk + 1]) / 2
    if "--peaks" in sys.argv:
        allpk, _ = find_peaks(h, height=0.1 * h.max(), distance=4)
        print("PEAKS near", round(fixed, 3), ":", [(round(float((e[k] + e[k + 1]) / 2), 3), round(float(h[k] / h.max()), 2)) for k in allpk])
    room_side = centre[1] if horiz else centre[0]
    f = c.max() if room_side > fixed else c.min()
    near = v[np.abs(v - f) < 0.02]
    wide = int((h >= 0.5 * h.max()).sum()) * bin_m
    rivals = [k for k in find_peaks(h, height=0.5 * h.max(), distance=4)[0] if abs((e[k] + e[k + 1]) / 2 - f) > 0.04]
    clean = wide <= 0.05 and not rivals
    return (float(np.median(near)) if len(near) > 10 else float(f)), clean


rows, ceil_rows, door_rows = [], [], []
for r in plan["rooms"]:
    if len(r["walls"]) != 4:
        continue
    corners = _apply(M, [w["start"] for w in r["walls"]])
    centre = corners.mean(0)
    fc = [laser_face(corners[i], corners[(i + 1) % 4], centre) for i in range(4)]
    faces = [x[0] for x in fc]; cleans = [x[1] for x in fc]
    for i in range(4):
        p, q = corners[i], corners[(i + 1) % 4]; horiz = abs(q[1] - p[1]) < abs(q[0] - p[0])
        ours_pos = (p[1] + q[1]) / 2 if horiz else (p[0] + q[0]) / 2
        inward = (centre[1] if horiz else centre[0]) - ours_pos
        if faces[i] is not None:
            print(f'SIDE {r["room_id"]} side{i} ours={ours_pos:.3f} laser_face={faces[i]:.3f} -> ours is {np.sign(inward) * (faces[i] - ours_pos) * 100:+.1f} cm OUTSIDE the wall (+ = room too big)')
    for i in range(4):
        # side i length is bounded by faces of sides i-1 and i+1 (the two perpendicular walls)
        a, b = faces[(i - 1) % 4], faces[(i + 1) % 4]
        ours = r["walls"][i]["length_m"]
        if a is None or b is None:
            rows.append({"room": r["room_id"], "wall": i, "ours_m": round(ours["value"], 4), "gt_m": None}); continue
        gt = abs(a - b)
        rows.append({"room": r["room_id"], "wall": i, "ours_m": round(ours["value"], 4), "gt_m": round(gt, 4),
                     "err_cm": round((ours["value"] - gt) * 100, 2), "err_pct": round((ours["value"] - gt) / gt * 100, 2),
                     "covered": bool(ours["lo"] <= gt <= ours["hi"]),
                     "clean_gt": bool(cleans[(i - 1) % 4] and cleans[(i + 1) % 4])})
    if Lceil is not None:
        poly = Polygon(corners)
        inside = np.array([poly.contains(Point(x, z)) for x, z in Lceil[::50, [0, 2]]])
        yc = Lceil[::50][inside, 1] if inside.any() else np.array([])
        if len(yc) > 50:
            gt_c = float(np.median(yc) - hp.floor_y)
            ours_c = r["ceiling_height_m"]
            ceil_rows.append({"room": r["room_id"], "gt_m": round(gt_c, 4),
                              "ours_m": None if ours_c is None else round(ours_c["value"], 4),
                              "err_cm": None if ours_c is None else round((ours_c["value"] - gt_c) * 100, 2)})
    for o in r["openings"]:
        w = r["walls"][o["wall_index"]]
        s, e = np.array(w["start"]), np.array(w["end"]); d = (e - s) / max(np.linalg.norm(e - s), 1e-9)
        c = _apply(M, [s + d * (o["offset_m"]["value"] + o["width_m"]["value"] / 2)])[0]
        dl = _apply(M, [s, e]); along = "x" if abs(dl[1][0] - dl[0][0]) > abs(dl[1][1] - dl[0][1]) else "z"
        g = refine_width(Lband, {"center": (float(c[0]), float(c[1])), "along": along, "width_m": o["width_m"]["value"]})
        door_rows.append({"room": r["room_id"], "ours_m": round(o["width_m"]["value"], 4),
                          "gt_m": None if g is None else round(g[0], 4),
                          "err_cm": None if g is None else round((o["width_m"]["value"] - g[0]) * 100, 2)})

ok = [x for x in rows if x.get("gt_m")]
e = np.array([abs(x["err_cm"]) for x in ok]) if ok else np.array([np.nan])
summary = {"capture": plan["capture_id"], "laser_scans": [p.name for p in lasers], "registration": diag,
           "walls_scored": len(ok), "walls_total": len(rows), "median_abs_err_cm": round(float(np.nanmedian(e)), 2),
           "within_1cm": int((e <= 1).sum()), "within_2cm": int((e <= 2).sum()), "within_5cm": int((e <= 5).sum()),
           "within_1pct": int(sum(abs(x["err_pct"]) <= 1 for x in ok)),
           "clean_walls": len([x for x in ok if x.get("clean_gt")]),
           "clean_median_abs_err_cm": round(float(np.median([abs(x["err_cm"]) for x in ok if x.get("clean_gt")])), 2) if any(x.get("clean_gt") for x in ok) else None,
           "clean_within_2cm": int(sum(abs(x["err_cm"]) <= 2 for x in ok if x.get("clean_gt"))),
           "interval_coverage": round(float(np.mean([x["covered"] for x in ok])), 2) if ok else None,
           "laser_ceiling_global_m": None if hp.ceiling_height is None else round(hp.ceiling_height, 4)}
out = Path("benchmark/results/own"); out.mkdir(parents=True, exist_ok=True)
(out / f"laser_gt_{plan['capture_id']}.json").write_text(json.dumps({"summary": summary, "walls": rows,
                                                                       "ceilings": ceil_rows, "doors": door_rows}, indent=1))
print(json.dumps(summary, indent=1))
for x in rows: print(x)
for x in ceil_rows: print("ceiling", x)
for x in door_rows: print("door", x)


if "--plot" in sys.argv:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(12, 12))
    ax.scatter(Lband[::15, 0], Lband[::15, 2], s=0.2, c="0.6", label="laser wall band")
    Qt = _apply(M, Qband[::15][:, [0, 2]])
    ax.scatter(Qt[:, 0], Qt[:, 1], s=0.2, c="tab:orange", alpha=0.4, label="our LiDAR wall band")
    for r in plan["rooms"]:
        c = _apply(M, [w["start"] for w in r["walls"]] + [r["walls"][0]["start"]])
        ax.plot(c[:, 0], c[:, 1], "b-", lw=2); ax.text(c[:-1, 0].mean(), c[:-1, 1].mean(), r["room_id"], color="b")
    ax.set_aspect("equal"); ax.legend(markerscale=20); plt.tight_layout()
    plt.savefig(out / f"laser_gt_{plan['capture_id']}.png", dpi=80)