"""Render the stitched plan to SVG: rooms, dimensioned walls with intervals, adjacency, warnings."""
from __future__ import annotations
from pathlib import Path
import svgwrite

from .models import PropertyPlan

PALETTE = ["#cfe8f3", "#f3e1cf", "#d9f3cf", "#f3cfe6", "#e6e1f7", "#f7f2c8", "#d3f0ec", "#f0d3d3"]


def to_svg(plan: PropertyPlan, out: Path, px_per_m: float = 90, margin: float = 1.0) -> None:
    pts = [tuple(w.start) for r in plan.rooms for w in r.walls]
    if not pts:
        svgwrite.Drawing(str(out), size=(200, 60)).save(); return
    x0 = min(p[0] for p in pts) - margin; x1 = max(p[0] for p in pts) + margin
    z0 = min(p[1] for p in pts) - margin; z1 = max(p[1] for p in pts) + margin
    W, H = (x1 - x0) * px_per_m, (z1 - z0) * px_per_m + 60
    tx = lambda x: (x - x0) * px_per_m
    tz = lambda z: (z1 - z) * px_per_m          # flip so +z is up on screen
    d = svgwrite.Drawing(str(out), size=(f"{W:.0f}px", f"{H:.0f}px"))
    d.add(d.rect((0, 0), (W, H), fill="white"))
    for k, r in enumerate(plan.rooms):
        poly = [(tx(w.start[0]), tz(w.start[1])) for w in r.walls]
        d.add(d.polygon(poly, fill=PALETTE[k % len(PALETTE)], stroke="#222", stroke_width=3))
        cx = sum(p[0] for p in poly) / len(poly); cy = sum(p[1] for p in poly) / len(poly)
        ceil = r.ceiling_height_m
        lines = [r.room_id, f"{r.floor_area_m2.value:.2f} m²"]
        lines.append(f"h {ceil.value:.3f} m" if ceil else "h n/a")
        for i, t in enumerate(lines):
            d.add(d.text(t, insert=(cx, cy + (i - 1) * 16), text_anchor="middle", font_size=14 if i == 0 else 12,
                         font_family="Arial", font_weight="bold" if i == 0 else "normal"))
        for w in r.walls:
            if w.length_m.value < 0.3:
                continue
            mx, mz = (w.start[0] + w.end[0]) / 2, (w.start[1] + w.end[1]) / 2
            hw = (w.length_m.hi - w.length_m.lo) / 2
            d.add(d.text(f"{w.length_m.value:.2f}±{hw*100:.0f}cm", insert=(tx(mx), tz(mz) - 4), text_anchor="middle",
                         font_size=10, font_family="Arial", fill="#1a4f8b"))
    fp = plan.footprint_m2
    footer = f"{plan.capture_id} | tier {plan.tier} | footprint {fp.value:.1f} m² ±{(fp.hi-fp.lo)/2:.1f}" if fp else plan.capture_id
    d.add(d.text(footer, insert=(10, H - 35), font_size=13, font_family="Arial"))
    if plan.warnings:
        d.add(d.text(f"{len(plan.warnings)} warning(s): see plan.json", insert=(10, H - 15), font_size=11,
                     font_family="Arial", fill="#b00"))
    d.save()
