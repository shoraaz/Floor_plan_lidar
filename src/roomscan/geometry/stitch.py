"""Whole-property stitching checks: footprint, overlaps, adjacency sanity.

LiDAR/video: rooms already share one world frame (single walk), so stitching = validation + footprint.
Photo tier will place rooms here via shared-opening constraints.
"""
from __future__ import annotations
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..models import PropertyPlan, Interval


def room_polygon(room) -> Polygon:
    pts = [tuple(w.start) for w in room.walls]
    return Polygon(pts).buffer(0)


def finalize(plan: PropertyPlan, overlap_tol_m2: float = 0.05) -> PropertyPlan:
    polys = {r.room_id: room_polygon(r) for r in plan.rooms}
    ids = list(polys)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            inter = polys[ids[i]].intersection(polys[ids[j]]).area
            if inter > overlap_tol_m2:
                plan.warnings.append(f"overlap {ids[i]}/{ids[j]}: {inter:.2f} m2")
    if polys:
        fp = unary_union(list(polys.values())).area
        # footprint interval: combine per-room area half-widths (conservative linear sum)
        hw = sum((r.floor_area_m2.hi - r.floor_area_m2.lo) / 2 for r in plan.rooms)
        plan.footprint_m2 = Interval.from_abs(fp, hw, unit="m2")
    for r in plan.rooms:
        r.floor_area_m2.unit = "m2"
    linked = {a for e in plan.adjacency for a in e}
    for rid in ids:
        if len(ids) > 1 and rid not in linked:
            plan.warnings.append(f"{rid}: no adjacency found (isolated room)")
    return plan
