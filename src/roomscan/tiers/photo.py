"""Photo tier: per-room photo folders -> stitched whole-property plan. The floor.

Plan:
 1. Per room: EXIF focal length -> intrinsics; metric monocular depth (Depth Pro / UniDepth);
    plane-based layout fit (rectilinear prior) -> wall lengths, ceiling height.
 2. Scale sanity: door-height prior (~2.04 m), standard ceiling priors; disagree -> widen interval.
 3. Openings: 2D door/window detection; record which openings are visible from more than one room.
 4. Cross-room: constraint layout (shared door alignment, no overlaps) in geometry/stitch.py.
 5. Input-quality gate: too few photos, blur, mirrors/glass, low light -> wide intervals or refuse.
"""
from __future__ import annotations
from pathlib import Path
from ..models import PropertyPlan


def run(capture: Path, drift_correction: bool = True) -> PropertyPlan:
    raise NotImplementedError("Photo tier not implemented yet")
