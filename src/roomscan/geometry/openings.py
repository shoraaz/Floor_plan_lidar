"""Openings: doorways detected during segmentation -> refined widths -> attached to room walls.

A doorway is emitted only when it connects two rooms (an unconnected gap is more often a phantom, and the gate
counts a phantom opening as a miss). Width is re-measured from raw wall-band points: along the wall line, the
empty run between the two door-frame faces, at 5 mm bins. Windows are not detected in this version.
"""
from __future__ import annotations
import numpy as np

from ..models import Opening, Interval


def _merge(doors: list[dict], tol: float = 0.3) -> list[dict]:
    out = []
    for d in sorted(doors, key=lambda d: -d["width_m"]):
        if any(np.hypot(d["center"][0] - o["center"][0], d["center"][1] - o["center"][1]) < tol for o in out):
            continue
        out.append(d)
    return out


def refine_width(band: np.ndarray, d: dict, bin_m: float = 0.005, slab: float = 0.12, reach: float = 0.5):
    """Return (width, centre_along, n_points) from the gap between door-frame faces, or None."""
    cx, cz = d["center"]
    if d["along"] == "x":            # door gap runs along x, wall at ~constant z
        run, fixed, c_run, c_fix = 0, 2, cx, cz
    else:
        run, fixed, c_run, c_fix = 2, 0, cz, cx
    half = d["width_m"] / 2 + reach
    sel = band[(np.abs(band[:, fixed] - c_fix) < slab) & (np.abs(band[:, run] - c_run) < half)]
    if len(sel) < 50:
        return None
    edges = np.arange(c_run - half, c_run + half + bin_m, bin_m)
    h, _ = np.histogram(sel[:, run], bins=edges)
    occ = h >= 2
    mid = len(h) // 2
    if occ[mid]:                      # centre bin occupied: not a clean gap at this height
        return None
    left = np.flatnonzero(occ[:mid]); right = np.flatnonzero(occ[mid:])
    if len(left) == 0 or len(right) == 0:
        return None
    a = edges[left[-1] + 1]; b = edges[mid + right[0]]
    return float(b - a), float((a + b) / 2), int(len(sel))


def attach_openings(rooms, geoms, doors, lab_to_id, band: np.ndarray, base_halfwidth: float = 0.01):
    by_id = {r.room_id: r for r in rooms}
    geo_by_id = {lab_to_id[g.label]: g for g in geoms if g.label in lab_to_id}
    emitted = 0
    for d in _merge([d for d in doors if len(d.get("rooms", [])) == 2]):
        ids = [lab_to_id.get(l) for l in d["rooms"]]
        if None in ids:
            continue
        ref = refine_width(band, d)
        if ref is None:
            width, centre, n = d["width_m"], (d["center"][0] if d["along"] == "x" else d["center"][1]), 0
            hw = 0.05                                     # grid-only estimate: wide interval
        else:
            width, centre, n = ref
            hw = base_halfwidth + 0.005
        if not 0.5 <= width <= 1.4:
            continue
        for rid, other in ((ids[0], ids[1]), (ids[1], ids[0])):
            g = geo_by_id[rid]; room = by_id[rid]
            best = None
            for i in range(len(g.polygon)):
                p, q = g.polygon[i], g.polygon[(i + 1) % len(g.polygon)]
                horiz = abs(q[1] - p[1]) < abs(q[0] - p[0])
                if (d["along"] == "x") != horiz:
                    continue
                fixed = p[1] if horiz else p[0]
                c_fix = d["center"][1] if horiz else d["center"][0]
                lo, hi = sorted([p[0], q[0]] if horiz else [p[1], q[1]])
                if lo - 0.2 <= centre <= hi + 0.2 and abs(fixed - c_fix) < 0.45:
                    dist = abs(fixed - c_fix)
                    if best is None or dist < best[0]:
                        start = p[0] if horiz else p[1]
                        best = (dist, i, abs(centre - start) - width / 2)
            if best is None:
                continue
            _, wi, off = best
            room.openings.append(Opening(kind="door", wall_index=int(wi), offset_m=Interval.from_abs(max(off, 0.0), 0.03),
                                         width_m=Interval.from_abs(width, hw), connects_to_room=other,
                                         confidence=1.0 if n else 0.5))
            emitted += 1
    return emitted
