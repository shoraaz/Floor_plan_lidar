"""Compare a tier's plan against the LiDAR plan of the same capture (LiDAR = reference; no tape ground truth
was provided with the sample data, so this measures cross-tier agreement, not absolute accuracy).

Alignment: both plans are gravity-aligned and Manhattan-aligned, so only a 90-degree rotation and a
translation separate them; found by FFT correlation of the room-union rasters (5 cm), all 4 rotations.
Rooms matched by IoU; rectangle rooms compared on their two wall lengths (x and z extents), with the tier's
interval checked for whether it contains the LiDAR value.

uv run python scripts/tier_compare.py <lidar_plan.json> <tier_plan.json>
"""
import sys, json
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve
from shapely.geometry import Polygon
from shapely import affinity

RES = 0.05


def polys(plan):
    return [(r, Polygon([w["start"] for w in r["walls"]]).buffer(0)) for r in plan["rooms"]]


def raster(ps, x0, z0, shape):
    from matplotlib.path import Path as MP
    G = np.zeros(shape, np.float32)
    zz, xx = np.mgrid[0:shape[0], 0:shape[1]]
    pts = np.c_[x0 + (xx.ravel() + .5) * RES, z0 + (zz.ravel() + .5) * RES]
    for _, p in ps:
        if p.is_empty:
            continue
        G.ravel()[MP(np.array(p.exterior.coords)).contains_points(pts)] = 1
    return G


def bounds(ps):
    b = np.array([p.bounds for _, p in ps if not p.is_empty])
    return b[:, 0].min(), b[:, 1].min(), b[:, 2].max(), b[:, 3].max()


def align(ref, tier):
    x0, z0, x1, z1 = bounds(ref)
    GA = raster(ref, x0, z0, (int((z1 - z0) / RES) + 2, int((x1 - x0) / RES) + 2))
    best = None
    for k in range(4):
        rot = [(r, affinity.rotate(p, 90 * k, origin=(0, 0))) for r, p in tier]
        bx0, bz0, bx1, bz1 = bounds(rot)
        GB = raster(rot, bx0, bz0, (int((bz1 - bz0) / RES) + 2, int((bx1 - bx0) / RES) + 2))
        c = fftconvolve(GA, GB[::-1, ::-1], mode="full")
        i = np.unravel_index(np.argmax(c), c.shape)
        dx = x0 - bx0 + (i[1] - (GB.shape[1] - 1)) * RES; dz = z0 - bz0 + (i[0] - (GB.shape[0] - 1)) * RES
        score = c[i] / max(GA.sum(), GB.sum())
        if best is None or score > best[0]:
            best = (score, k, dx, dz)
    score, k, dx, dz = best
    return [(r, affinity.translate(affinity.rotate(p, 90 * k, origin=(0, 0)), dx, dz)) for r, p in tier], score, k


def main(ref_p, tier_p):
    ref_plan, tier_plan = json.loads(Path(ref_p).read_text()), json.loads(Path(tier_p).read_text())
    ref, tier = polys(ref_plan), polys(tier_plan)
    tier_al, score, k = align(ref, tier)
    rows = []
    for rt, pt in tier_al:
        if len(rt["walls"]) != 4:
            continue
        best = max(ref, key=lambda t: pt.intersection(t[1]).area / max(pt.union(t[1]).area, 1e-9))
        iou = pt.intersection(best[1]).area / pt.union(best[1]).area
        if iou < 0.4 or len(best[0]["walls"]) != 4:
            continue
        # after a 90-deg rotation the tier's x wall corresponds to the reference's z wall
        tw = [rt["walls"][0]["length_m"], rt["walls"][1]["length_m"]]
        if k % 2 == 1:
            tw = tw[::-1]
        rw = [best[0]["walls"][0]["length_m"]["value"], best[0]["walls"][1]["length_m"]["value"]]
        for t, r_ in zip(tw, rw):
            rows.append({"room": rt["room_id"], "ref_room": best[0]["room_id"], "iou": round(iou, 2),
                         "tier_m": round(t["value"], 3), "lo": round(t["lo"], 3), "hi": round(t["hi"], 3),
                         "lidar_m": round(r_, 3), "err_pct": round((t["value"] - r_) / r_ * 100, 1),
                         "covered": bool(t["lo"] <= r_ <= t["hi"])})
    fa = ref_plan["footprint_m2"]["value"]; fb = tier_plan["footprint_m2"]["value"]
    errs = np.array([abs(r["err_pct"]) for r in rows]) if rows else np.array([np.nan])
    summary = {"tier": tier_plan["tier"], "capture": tier_plan["capture_id"], "align_overlap": round(float(score), 3),
               "rooms_tier": len(tier), "rooms_lidar": len(ref), "footprint_tier_m2": round(fb, 2),
               "footprint_lidar_m2": round(fa, 2), "footprint_err_pct": round((fb - fa) / fa * 100, 1),
               "matched_dims": len(rows), "median_abs_err_pct": round(float(np.nanmedian(errs)), 1),
               "within_3pct": int((errs <= 3).sum()), "within_8pct": int((errs <= 8).sum()),
               "interval_coverage": round(float(np.mean([r["covered"] for r in rows])), 2) if rows else None}
    return summary, rows


if __name__ == "__main__":
    s, rows = main(sys.argv[1], sys.argv[2])
    print(json.dumps(s))
    for r in rows:
        print(r)
