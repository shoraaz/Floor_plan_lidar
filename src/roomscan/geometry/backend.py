"""Shared geometry backend: any metric, roughly gravity-aligned (y-up) point cloud -> PropertyPlan.

All three tiers end here, so the room logic, intervals and output contract are identical; tiers differ only
in how they produce (points, camera centres, per-frame ray endpoints) and in their calibration entries.
"""
from __future__ import annotations
import numpy as np

from ..models import PropertyPlan, Room, Wall, Interval
from .. import calibration


def plan_from_cloud(P: np.ndarray, cams: np.ndarray, rays: list[np.ndarray], capture_id: str, tier: str,
                    warnings: list[str] | None = None, extra_quality: dict | None = None,
                    quality_scale: float = 1.0) -> PropertyPlan:
    from .planes import horizontal_planes, estimate_yaw, rotate_y
    from .rooms import segment_structure_v2
    from .snap import snap_rooms_rect

    warnings = list(warnings or [])
    hp = horizontal_planes(P, cam_y=float(np.median(cams[:, 1])))
    yaw, yinfo = estimate_yaw(P, hp)
    P, cams = rotate_y(P, yaw), rotate_y(cams, yaw)
    rays = [rotate_y(r, yaw) for r in rays]
    g, labels, wall, free, doors, flags = segment_structure_v2(P, cams, rays, hp.floor_y, hp.ceiling_y)
    geoms, shapes = snap_rooms_rect(g, labels, P, hp.floor_y, hp.ceiling_y, wall)

    cal = calibration.load()[tier]
    rooms = []
    for k, rg in enumerate(geoms, 1):
        n = len(rg.polygon)
        enclosed = flags.get(rg.label, {}).get("enclosed", True)
        walls = []
        for i in range(n):
            p, q = rg.polygon[i], rg.polygon[(i + 1) % n]
            qs = max(rg.wall_support[i], 0.15) * quality_scale * (1.0 if enclosed else 0.5)
            walls.append(Wall(p, q, Interval.from_rel(rg.wall_lengths[i], calibration.inflate(cal["wall"], qs))))
        if rg.ceiling_height is not None:
            half = max(cal["ceiling"] * rg.ceiling_height / max(quality_scale, 0.15), 2 * (rg.ceiling_spread or 0.0))
            ceil = Interval.from_abs(rg.ceiling_height, half)
        else:
            ceil = None
            warnings.append(f"room{k}: ceiling not observed in capture; ceiling height not reported")
        if not enclosed:
            warnings.append(f"room{k}: not enclosed by detected walls; extent from observed space only (intervals widened)")
        if shapes.get(rg.label, {}).get("shape") == "rectilinear":
            warnings.append(f"room{k}: non-rectangular room; rectilinear outline used")
        rooms.append(Room(room_id=f"room{k}", walls=walls, ceiling_height_m=ceil,
                          floor_area_m2=Interval.from_rel(rg.area_m2, calibration.inflate(cal["area"], quality_scale))))

    lab_to_id = {rg.label: f"room{k}" for k, rg in enumerate(geoms, 1)}
    adj = set()
    for d in doors:
        ids = [lab_to_id[l] for l in d.get("rooms", []) if l in lab_to_id]
        if len(ids) == 2:
            adj.add(tuple(sorted(ids)))

    quality = {"frames": int(len(cams)), "manhattan_concentration": round(yinfo["coarse_concentration"], 3),
               "floor_spread_m": round(hp.floor_spread_m, 4),
               "loop_gap_m": round(float(np.linalg.norm(cams[-1] - cams[0])), 3),
               "yaw_deg": round(float(np.degrees(yaw)), 3), "yaw_refine_delta_deg": round(yinfo["delta_deg"], 3)}
    quality.update(extra_quality or {})
    return PropertyPlan(capture_id=capture_id, tier=tier, rooms=rooms, adjacency=sorted(adj), warnings=warnings,
                        input_quality=quality)
