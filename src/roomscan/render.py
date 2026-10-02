"""Render stitched plan to SVG (rooms, walls, openings, dimensions)."""
from pathlib import Path
from .models import PropertyPlan


def to_svg(plan: PropertyPlan, out: Path) -> None:
    # TODO: svgwrite rendering with dimension labels and interval hints.
    Path(out).write_text("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"10\" height=\"10\"/>")
