"""Repeatability: two captures of the same place at the same tier -> per-wall agreement table.

Gate (PDF): two captures of the same room at the same tier agree within 1 cm OR 0.5% per wall.

Steps
  1. Rebuild each capture's Manhattan-aligned wall-band cloud (cached, deterministic).
  2. Register B onto A: 4 x 90deg rotations x FFT translation search (5 cm), then 2D ICP refine.
  3. Transform B's room polygons into A's frame, match rooms by IoU.
  4. Match walls inside matched rooms (same orientation, nearby face), compare length and face position.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import open3d as o3d
from scipy.signal import fftconvolve
from shapely.geometry import Polygon

from ..tiers.lidar import fused
from ..geometry.planes import horizontal_planes, manhattan_yaw, rotate_y, wall_slice

RES = 0.05


def aligned_band(capture: Path) -> np.ndarray:
    P, cams, _ = fused(capture)
    hp = horizontal_planes(P, cam_y=float(np.median(cams[:, 1])))
    yaw, _ = manhattan_yaw(wall_slice(P, hp))
    P = rotate_y(P, yaw)
    return P[(P[:, 1] > hp.floor_y + 1.1) & (P[:, 1] < hp.floor_y + 2.0)][:, [0, 2]]


def _grid(B, x0, z0, shape):
    G = np.zeros(shape, np.float32)
    c = ((B[:, 0] - x0) / RES).astype(int); r = ((B[:, 1] - z0) / RES).astype(int)
    ok = (r >= 0) & (r < shape[0]) & (c >= 0) & (c < shape[1])
    np.add.at(G, (r[ok], c[ok]), 1)
    return (G >= 2).astype(np.float32)


def register(A: np.ndarray, B: np.ndarray):
    """Return 3x3 homogeneous 2D transform mapping B -> A, plus diagnostics."""
    a0 = A.min(0); shA = (int(np.ptp(A[:, 1]) / RES) + 2, int(np.ptp(A[:, 0]) / RES) + 2)
    GA = _grid(A, a0[0], a0[1], shA)
    best = None
    for k in range(4):
        th = k * np.pi / 2
        Rm = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
        Br = B @ Rm.T
        b0 = Br.min(0); shB = (int(np.ptp(Br[:, 1]) / RES) + 2, int(np.ptp(Br[:, 0]) / RES) + 2)
        GB = _grid(Br, b0[0], b0[1], shB)
        corr = fftconvolve(GA, GB[::-1, ::-1], mode="full")
        i = np.unravel_index(np.argmax(corr), corr.shape)
        s_r, s_c = i[0] - (shB[0] - 1), i[1] - (shB[1] - 1)
        t = a0 - b0 + np.array([s_c, s_r]) * RES
        score = corr[i] / min(GA.sum(), GB.sum())
        if best is None or score > best[0]:
            best = (score, k, Rm, t)
    score, k, Rm, t = best
    T0 = np.eye(4); T0[0, 0], T0[0, 2], T0[2, 0], T0[2, 2] = Rm[0, 0], Rm[0, 1], Rm[1, 0], Rm[1, 1]
    T0[0, 3], T0[2, 3] = t
    to3 = lambda X: o3d.geometry.PointCloud(o3d.utility.Vector3dVector(np.c_[X[:, 0], np.zeros(len(X)), X[:, 1]]))
    pa, pb = to3(A).voxel_down_sample(0.02), to3(B).voxel_down_sample(0.02)
    T = T0
    for thr in (0.15, 0.05, 0.02):
        r = o3d.pipelines.registration.registration_icp(pb, pa, thr, T,
                                                        o3d.pipelines.registration.TransformationEstimationPointToPoint())
        T = r.transformation
    # project to a pure planar rigid motion (rotation about y + x/z translation)
    ang = np.arctan2(T[0, 2], T[0, 0])
    c, s = np.cos(ang), np.sin(ang)
    M = np.array([[c, s, T[0, 3]], [-s, c, T[2, 3]], [0, 0, 1]])
    return M, {"coarse_overlap": float(score), "coarse_rot_deg": int(k * 90), "icp_fitness": float(r.fitness),
               "icp_rmse_m": float(r.inlier_rmse), "residual_rot_deg": float((np.degrees(ang) + 45) % 90 - 45)}


def _apply(M, pts):
    P = np.c_[np.asarray(pts, float), np.ones(len(pts))]
    return (P @ M.T)[:, :2]


def _walls(room):
    return [(np.array(w["start"], float), np.array(w["end"], float), w["length_m"]["value"]) for w in room["walls"]]


def compare(plan_a: dict, plan_b: dict, M: np.ndarray, min_iou: float = 0.5, min_wall_m: float = 0.5):
    rooms_b = []
    for rb in plan_b["rooms"]:
        ws = [(*_apply(M, [s, e]), L) for s, e, L in _walls(rb)]
        rooms_b.append((rb, Polygon([w[0] for w in ws]).buffer(0), ws))
    rows, room_rows = [], []
    for ra in plan_a["rooms"]:
        pa = Polygon([w["start"] for w in ra["walls"]]).buffer(0)
        best = max(rooms_b, key=lambda x: pa.intersection(x[1]).area / max(pa.union(x[1]).area, 1e-9), default=None)
        iou = pa.intersection(best[1]).area / pa.union(best[1]).area if best else 0.0
        room_rows.append({"room_a": ra["room_id"], "room_b": best[0]["room_id"] if best else None, "iou": round(iou, 3),
                          "area_a": round(ra["floor_area_m2"]["value"], 3),
                          "area_b": round(best[0]["floor_area_m2"]["value"], 3) if best else None})
        if not best or iou < min_iou:
            continue
        rb, _, wsb = best
        for sa, ea, La in _walls(ra):
            if La < min_wall_m:
                continue
            horiz = abs(ea[1] - sa[1]) < 1e-6
            fixed = sa[1] if horiz else sa[0]
            cand = []
            for sb, eb, Lb in wsb:
                hb = abs(eb[1] - sb[1]) < abs(eb[0] - sb[0])
                if hb != horiz:
                    continue
                fb = (sb[1] + eb[1]) / 2 if horiz else (sb[0] + eb[0]) / 2
                ra_lo, ra_hi = sorted([sa[0], ea[0]] if horiz else [sa[1], ea[1]])
                rb_lo, rb_hi = sorted([sb[0], eb[0]] if horiz else [sb[1], eb[1]])
                ov = min(ra_hi, rb_hi) - max(ra_lo, rb_lo)
                if abs(fb - fixed) < 0.3 and ov > 0.5 * La:
                    cand.append((abs(fb - fixed), Lb, fb))
            if not cand:
                rows.append({"room": ra["room_id"], "wall_len_a": round(La, 4), "wall_len_b": None, "diff_cm": None,
                             "face_offset_cm": None, "pass": False, "note": "no matching wall in B"})
                continue
            off, Lb, fb = min(cand)
            diff = abs(La - Lb)
            ok = diff <= 0.01 or diff <= 0.005 * La
            rows.append({"room": ra["room_id"], "wall_len_a": round(La, 4), "wall_len_b": round(Lb, 4),
                         "diff_cm": round(diff * 100, 2), "face_offset_cm": round(off * 100, 2), "pass": bool(ok), "note": ""})
    return room_rows, rows


def ceiling_spread(plans: list[dict]):
    """Per-room ceiling spread across captures (only rooms with observed ceilings)."""
    return [r["ceiling_height_m"]["value"] for p in plans for r in p["rooms"] if r["ceiling_height_m"]]


def report(cap_a: Path, cap_b: Path, plan_a_path: Path, plan_b_path: Path, out: Path):
    A, B = aligned_band(cap_a), aligned_band(cap_b)
    M, diag = register(A, B)
    pa, pb = json.loads(plan_a_path.read_text()), json.loads(plan_b_path.read_text())
    room_rows, rows = compare(pa, pb, M)
    n = len(rows); npass = sum(r["pass"] for r in rows)
    fa, fb = pa["footprint_m2"]["value"], pb["footprint_m2"]["value"]
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Repeatability (LiDAR tier): {pa['capture_id']} vs {pb['capture_id']}", "",
             f"Registration: coarse overlap {diag['coarse_overlap']:.3f} at {diag['coarse_rot_deg']} deg, "
             f"ICP fitness {diag['icp_fitness']:.3f}, inlier RMSE {diag['icp_rmse_m']*100:.2f} cm", "",
             f"Footprint: {fa:.2f} vs {fb:.2f} m2 (diff {abs(fa-fb)/fa*100:.2f}%)", "",
             f"**Wall gate (<=1 cm or <=0.5%): {npass}/{n} walls pass**", "",
             "## Room matching", "", "| room A | room B | IoU | area A | area B |", "|---|---|---|---|---|"]
    lines += [f"| {r['room_a']} | {r['room_b']} | {r['iou']} | {r['area_a']} | {r['area_b']} |" for r in room_rows]
    lines += ["", "## Walls (rooms with IoU >= 0.5)", "", "| room | len A (m) | len B (m) | diff (cm) | face offset (cm) | pass | note |",
              "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['room']} | {r['wall_len_a']} | {r['wall_len_b']} | {r['diff_cm']} | {r['face_offset_cm']} | "
              f"{'PASS' if r['pass'] else 'FAIL'} | {r['note']} |" for r in rows]
    out.write_text("\n".join(lines))
    out.with_suffix(".json").write_text(json.dumps({"registration": diag, "rooms": room_rows, "walls": rows,
                                                    "walls_pass": npass, "walls_total": n}, indent=1))
    return npass, n, diag, room_rows
