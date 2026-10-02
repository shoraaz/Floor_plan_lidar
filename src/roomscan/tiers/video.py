"""Video tier: handheld walkthrough -> RoomGeometry (+ stitched plan).

Plan: sample keyframes -> poses (pycolmap or VGGT/MASt3R) -> metric scale from a metric
monocular depth model + door-height prior (~2.04 m) -> reuse plane/room code from geometry/.
Intervals come from calibration.py, inflated by input quality (blur, parallax, low light).
"""
from __future__ import annotations
from pathlib import Path
from ..models import PropertyPlan


def run(capture: Path, drift_correction: bool = True) -> PropertyPlan:
    raise NotImplementedError("Video tier not implemented yet")
